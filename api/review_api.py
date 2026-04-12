"""Email Review API - Returns JSON for email review operations"""

import logging
import json
import re
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from channels.email.review_store import (
    get_review_queue,
    get_review_email_by_id,
    remove_email_from_review
)
from channels.email.gmail_client import GmailClient
from channels.email.booking_email_sender import get_booking_email_sender
from scheduling.scheduler import book_slot
from knowledge_base.email_history_store import EmailHistoryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["review"])

gmail = GmailClient()
email_store = EmailHistoryStore()


class ReviewEmailItem(BaseModel):
    """Pending review email in queue"""
    id: int
    customer_email: str
    subject: str
    preview: str = ""
    received_at: Optional[str] = None
    urgency: str = ""


class ReviewQueueResponse(BaseModel):
    """Response with review queue"""
    queue: List[ReviewEmailItem]
    total: int
    message: str


class ReviewEmailDetailResponse(BaseModel):
    """Response with email detail for review"""
    email_id: int
    customer_email: str
    customer_question: str
    subject: str
    agent_reply: str
    selected_slot: Optional[str] = None
    has_appointment: bool
    thread_id: str
    message_id: str
    booking_pending: Optional[str] = None
    message: str = "Email detail retrieved"


class ReviewSubmitRequest(BaseModel):
    """Request to submit review and send email"""
    email_id: int
    customer_email: str
    customer_question: str
    agent_reply: str
    owner_correction: str = ""
    subject: str
    thread_id: str
    message_id: str
    references: str = ""  # CRITICAL: Include full conversation chain for Gmail threading
    in_reply_to: str = ""  # Include original reply context
    selected_slot: str = ""
    booking_pending: str = ""


class ReviewSubmitResponse(BaseModel):
    """Response from review submission"""
    status: str
    message: str
    booking_id: Optional[str] = None
    success: bool


@router.get("/queue", response_model=ReviewQueueResponse)
def get_review_queue_api():
    """
    Get list of pending emails awaiting owner review.
    
    Returns:
        List of emails in review queue
    """
    try:
        review_queue = get_review_queue()
        
        queue_items = []
        for email_data in review_queue:
            item = ReviewEmailItem(
                id=email_data.get("id", 0),
                customer_email=email_data.get("customer_email", ""),
                subject=email_data.get("subject", ""),
                preview=email_data.get("customer_question", "")[:100],
                received_at=email_data.get("timestamp"),
                urgency=email_data.get("urgency", "")
            )
            queue_items.append(item)
        
        return ReviewQueueResponse(
            queue=queue_items,
            total=len(queue_items),
            message="Review queue retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting review queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/detail/{email_id}", response_model=ReviewEmailDetailResponse)
def get_review_email_detail(email_id: int):
    """
    Get detailed information about a specific email for review.
    
    Args:
        email_id: Email ID to retrieve
        
    Returns:
        Email details for review
    """
    try:
        email_data = get_review_email_by_id(email_id)
        
        if not email_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not found in review queue"
            )
        
        # Debug logging for customer_email issue
        customer_email = email_data.get("customer_email", "") or ""  # Ensure never None
        customer_question = email_data.get("customer_question", "") or ""
        subject = email_data.get("subject", "") or ""
        agent_reply = email_data.get("agent_reply", "") or ""
        
        # Ensure booking_pending is a string or None (not a dict)
        booking_pending = email_data.get("booking_pending")
        if booking_pending and not isinstance(booking_pending, str):
            # If it's a dict (shouldn't happen now), convert to JSON string
            import json
            booking_pending = json.dumps(booking_pending)
        
        logger.debug(f"DEBUG: Retrieved email_id={email_id}, customer_email='{customer_email}' (type={type(customer_email).__name__})")
        logger.debug(f"DEBUG: Full email_data keys: {list(email_data.keys())}")
        if not customer_email:
            logger.warning(f"WARNING: customer_email is empty for email_id={email_id}. Full data: {email_data}")
        
        return ReviewEmailDetailResponse(
            email_id=email_id,
            customer_email=customer_email,
            customer_question=customer_question,
            subject=subject,
            agent_reply=agent_reply,
            selected_slot=email_data.get("selected_slot"),
            has_appointment=email_data.get("intent") == "appointment",  # Match the actual intent value
            thread_id=email_data.get("thread_id", ""),
            message_id=email_data.get("message_id", ""),
            booking_pending=booking_pending,
            message="Email detail retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/submit", response_model=ReviewSubmitResponse)
def submit_review_api(request: ReviewSubmitRequest):
    """
    Submit owner review and send final email.
    
    Handles:
    - Email sending via Gmail with threading
    - Optional booking confirmation with potentially modified slot
    - Email history update with final approved reply
    
    Args:
        request: Review submission details
        
    Returns:
        Response with submission status
    """
    try:
        corrected_reply = request.owner_correction.strip()
        final_reply = corrected_reply if corrected_reply else request.agent_reply
        modified_slot = request.selected_slot.strip() if request.selected_slot else ""
        
        # Step 1: Send final email via Gmail
        if not request.booking_pending:
            logger.info(f"Step 1: Sending non-appointment reply to {request.customer_email}")
            gmail.send_email_reply(
                to_email=request.customer_email,
                subject=request.subject,
                body=final_reply,
                thread_id=request.thread_id,
                message_id=request.message_id
            )
            logger.info(f"Escalated non-appointment email approved and sent to {request.customer_email}")
        else:
            logger.info(f"Step 1: Skipped (booking_pending is not empty) for {request.customer_email}")
        
        # Step 2: Save the FINAL approved reply to email_history
        email_store.save_email(
            customer_email=request.customer_email,
            sender_category="support",
            subject=f"Re: {request.subject}",
            body=final_reply,
            thread_id=request.thread_id,
            message_id=request.message_id,
            intent=None,
            channel="email"
        )
        logger.info(f"Saved approved email to history for {request.customer_email}")
        
        # Step 3: If this was a booking request, process the booking now
        booking_id = None
        if request.booking_pending:
            try:
                booking_info = json.loads(request.booking_pending)
                
                # Use owner-modified slot if provided, otherwise use AI-selected slot
                booking_slot = modified_slot if modified_slot else booking_info.get("selected_slot")
                
                # Log threading info for debugging
                logger.debug(f"DEBUG: Sending booking confirmation - thread_id='{request.thread_id}', message_id='{request.message_id}'")
                
                # Create booking with (potentially modified) slot
                booking = book_slot(
                    customer_email=request.customer_email,
                    slot=booking_slot,
                    channel="email",
                    notes=f"Booking approved by owner from email: {request.customer_question[:100]}",
                    days_ahead=14
                )
                
                if booking.get("status") == "confirmed":
                    booking_id = booking.get("id")
                    logger.info(f"Booking confirmed: {booking_id} for {request.customer_email} at {booking_slot}")
                    
                    # Send booking confirmation email with .ics
                    email_sender = get_booking_email_sender()
                    
                    # For To header: use request.customer_email as-is for Gmail threading compatibility
                    # Gmail needs the original From header format to recognize as reply
                    customer_name = request.customer_email.split('@')[0] if '@' in request.customer_email else request.customer_email.split('<')[-1].rstrip('>')
                    
                    # Enhanced body with booking details
                    email_body = f"""{final_reply}

---
Appointment Details:
Time: {booking_slot}
Status: Confirmed

To reschedule, please reply directly to this email."""
                    
                    success, result = email_sender.send_booking_confirmation_with_ics(
                        customer_email=request.customer_email,  # Use original format for Gmail threading
                        customer_name=customer_name,
                        appointment_slot=booking_slot,
                        thread_id=request.thread_id,
                        message_id=request.message_id,
                        original_subject=request.subject,  # OpenAI Fix: Use original subject from incoming email
                        original_references=request.references,  # OpenAI Fix: Pass complete conversation chain
                        email_body=email_body,
                        subject=f"Appointment Confirmed - {request.subject}"
                    )
                    
                    if success:
                        logger.info(f"Booking confirmation email sent to {request.customer_email}")
                    else:
                        logger.warning(f"Failed to send booking confirmation email to {request.customer_email}: {result}")
                else:
                    logger.warning(f"Booking failed: {booking.get('reason', 'unknown error')}")
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid booking_pending JSON: {request.booking_pending}")
            except Exception as e:
                logger.error(f"Error processing booking: {e}", exc_info=True)
        
        # Step 4: Remove email from review queue
        try:
            remove_email_from_review(request.email_id)
            logger.info(f"Email {request.email_id} removed from review queue")
        except Exception as e:
            logger.warning(f"Failed to remove email from review queue: {e}")
        
        return ReviewSubmitResponse(
            status="success",
            message="Email review submitted successfully",
            booking_id=booking_id,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error submitting review: {e}", exc_info=True)
        return ReviewSubmitResponse(
            status="error",
            message=str(e),
            booking_id=None,
            success=False
        )
