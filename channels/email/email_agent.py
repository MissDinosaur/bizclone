import logging
import json
from channels.email.parser import parse_email
from model.intent_classifier import IntentClassifier
from channels.email.review_store import add_email_to_review
from channels.email.urgency_detector import UrgencyDetector
from scheduling.appointment_workflow import EmailAppointmentWorkflow
from rag.rag_pipeline import EmailRAGPipeline
from scheduling.booking_manager import BookingManager
from scheduling.scheduling_config import SchedulingConfig
from channels.email.email_history_store import EmailHistoryStore
from channels.schemas import (
    ChannelMessageResponseSchema,
    IntentType,
    MessageStatus,
    BookingResponseSchema,
    intent_to_enum,
)
import config.config as cfg

logger = logging.getLogger(__name__)

""" Email Agent Orchestrator (End-to-End Brain) """


def _intent_to_enum(intent_str: str) -> IntentType:
    """
    Backward-compatible wrapper around channels.schemas.intent_to_enum.
    """
    return intent_to_enum(intent_str)


class EmailAgent:
    """
    Email message processor.
    Handles the end-to-end email pipeline:
    1. Parse incoming email
    2. Predict intent using NLP model (15 categories)
    3. Detect urgency level (CRITICAL/HIGH/NORMAL) - INDEPENDENT of intent
    4. Retrieve relevant KB context (RAG)
    5. Generate final reply draft using LLM
    6. Handle scheduling requests (appointments, cancellations, reschedules)
    """

    def __init__(self, db_session=None):
        self.rag = EmailRAGPipeline()
        self.intent_model = IntentClassifier()
        self.urgency_detector = UrgencyDetector()
        self.email_store = EmailHistoryStore()
        self.scheduling_config = SchedulingConfig()
        # Always initialize BookingManager (it will create its own db_session if needed)
        self.booking_manager = BookingManager(db_session=db_session)
        self.appointment_workflow = EmailAppointmentWorkflow(
            scheduling_config=self.scheduling_config,
            booking_manager=self.booking_manager
        )

    def process_email(self, email_payload: dict) -> ChannelMessageResponseSchema:
        """
        End-to-end Email Agent pipeline.
        Args:
            email_payload: Email dict with keys: from, subject, body, thread_id, message_id 
        Returns:
            ChannelMessageResponseSchema with response details
        """

        # Step 1: Parse email payload
        parsed = parse_email(email_payload)
        email_text = parsed["text"]
        customer_email = email_payload["from"]
        subject = email_payload.get("subject", "(no subject)")
        thread_id = email_payload.get("thread_id")
        message_id = email_payload.get("message_id")
        references = email_payload.get("references", "")  # CRITICAL: Extract full conversation chain
        in_reply_to = email_payload.get("in_reply_to", "")

        # Step 2: Intent Detection (NLP) - SEPARATE from urgency
        intent_result = self.intent_model.predict_intent(email_text)
        intent = intent_result["intent"]
        intent_confidence = intent_result["confidence"]
        logger.info(f"email - intent: {intent} ({intent_confidence:.0%})", extra={"channel": "email"})
        
        # Step 3: Urgency Detection (keyword-based) - INDEPENDENT of intent
        urgency_result = self.urgency_detector.detect_urgency(email_text, intent=intent)
        urgency_level = urgency_result["urgency_level"]
        urgency_confidence = urgency_result["confidence"]
        escalation_reason = urgency_result["escalation_reason"]
        detected_keywords = urgency_result["detected_keywords"]
        
        logger.info(f"email - urgency: {urgency_level} ({urgency_confidence:.0%}) - {escalation_reason}", extra={"channel": "email"})
        if detected_keywords:
            logger.warning(f"email - escalation keywords: {detected_keywords}", extra={"channel": "email"})

        # Step 4: Save incoming customer email to history
        self.email_store.save_email(
            customer_email=customer_email,
            sender_category="customer",
            subject=subject,
            body=email_text,
            thread_id=thread_id,
            message_id=message_id,
            intent=intent,
            channel="email"
        )

        # Step 5: Initialize response tracking variables
        booking_info = None
        booking_response = None
        booking_confirmation_sent = False
        reply_text = None
        retrieved_docs = None
        selected_slot = None
        llm_reasoning = None
        booking_info_pending = None  # Store pending booking for review if escalated
        
        # Step 6: Generate reply based on intent (with slot selection for appointments)
        if intent == "appointment":
            # For appointment requests: select slot FIRST, then generate reply with slot context
            logger.info("Processing appointment request - selecting best slot first")
            
            slot_selection_result = self.appointment_workflow.select_appointment_slot(
                customer_email=customer_email,
                email_text=email_text
            )
            
            logger.warning("Have selected appointment slot, generating standard reply")
            selected_slot = slot_selection_result["slot"]
            llm_reasoning = slot_selection_result["reasoning"]
            
            # Now generate reply with the selected slot as context
            reply_text, retrieved_docs = self.rag.generate_email_reply(
                customer_email=customer_email,
                body=email_text,
                intent=intent,
                booking={
                    "slot": selected_slot,
                    "reasoning": llm_reasoning
                }
            )
            
            # Store booking context for later (will send email only if not escalated)
            booking_info_pending = {
                "customer_email": customer_email,
                "message_text": email_text,
                "thread_id": thread_id,
                "message_id": message_id,
                "subject": subject,
                "selected_slot": selected_slot,
                "reply_text": reply_text
            }
        elif intent == "cancellation":
            # For cancellation requests: find and cancel existing booking completely
            logger.info("Processing cancellation request - completely cancelling appointment")
            
            # Generate reply first (will include cancellation details if booking found)
            reply_text, retrieved_docs = self.rag.generate_email_reply(
                customer_email=customer_email,
                body=email_text,
                intent=intent,
                booking=None
            )
            
            # Store cancellation context for later handling
            booking_info_pending = {
                "customer_email": customer_email,
                "message_text": email_text,
                "thread_id": thread_id,
                "message_id": message_id,
                "references": references,
                "subject": subject,
                "reply_text": reply_text,
                "is_cancellation": True
            }
        elif intent == "rescheduling":
            # For rescheduling requests: select the new slot first,
            # then generate the reply using that exact slot 
            # so email text, database, and ICS stay consistent.
            logger.info("Processing rescheduling request - selecting new appointment slot first")

            slot_selection_result = self.appointment_workflow.select_appointment_slot(
                customer_email=customer_email,
                email_text=email_text
            )

            selected_slot = slot_selection_result["slot"]
            llm_reasoning = slot_selection_result["reasoning"]

            reply_text, retrieved_docs = self.rag.generate_email_reply(
                customer_email=customer_email,
                body=email_text,
                intent=intent,
                booking={
                    "slot": selected_slot,
                    "reasoning": llm_reasoning
                }
            )

            # Store rescheduling context for later handling
            booking_info_pending = {
                "customer_email": customer_email,
                "message_text": email_text,
                "thread_id": thread_id,
                "message_id": message_id,
                "subject": subject,
                "reply_text": reply_text,
                "selected_slot": selected_slot,
                "is_rescheduling": True
            }
        else:
            # For non-appointment requests: use standard RAG + LLM pipeline
            reply_text, retrieved_docs = self.rag.generate_email_reply(
                customer_email=customer_email,
                body=email_text,
                intent=intent,
                booking=None
            )

        # Step 7: Handle escalation or send response
        # Urgency determines escalation, intent determines reply content
        should_escalate = self.urgency_detector.should_escalate_to_owner(urgency_level)
        
        if should_escalate:
            # ESCALATED: Add to review queue without saving draft reply yet
            # Owner may modify reply and/or appointment time before approval
            # Final reply will be saved AFTER owner approval
            logger.warning(f"email - [{urgency_level}] escalating to owner from {customer_email} for review", extra={"channel": "email"})
            logger.warning(f"email - reason: {escalation_reason}", extra={"channel": "email"})
            
            # Save email to review queue for owner to approve
            review_data = {
                "customer_email": customer_email,
                "subject": subject,
                "agent_reply": reply_text,
                "customer_question": email_text,
                "thread_id": thread_id,
                "message_id": message_id,
                "references": references,  # CRITICAL: Store full conversation chain for proper threading
                "in_reply_to": in_reply_to,  # Store original reply context
                "urgency_level": urgency_level,
                "escalation_reason": escalation_reason,
                "intent": intent,
                "booking_pending": json.dumps(booking_info_pending) if booking_info_pending else None,
                "selected_slot": selected_slot  # For owner to modify if appointment
            }
            add_email_to_review(review_data)
            logger.info(f"email - saved to review queue for owner approval")
            
            return ChannelMessageResponseSchema(
                channel="email",
                status=MessageStatus.NEEDS_REVIEW,
                intent=_intent_to_enum(intent),
                reply=reply_text,
                booking=None,  # No booking confirmation yet - pending owner review
                retrieved_docs=retrieved_docs,
                error_code=None,
                error_message=None,
                # Store booking context for owner to review
                metadata={
                    "urgency_level": urgency_level,
                    "urgency_confidence": urgency_confidence,
                    "escalation_reason": escalation_reason,
                    "detected_keywords": detected_keywords,
                    "intent_confidence": intent_confidence,
                    "booking_pending": booking_info_pending,  # Store booking for owner to approve
                    "selected_slot": selected_slot  # For owner to modify slot if needed
                }
            )
        else:
            # NOT ESCALATED: AUTO-SEND path
            # Send reply immediately via Gmail (with .ics if appointment)
            # Save the generated reply to history
            self.email_store.save_email(
                customer_email=customer_email,
                sender_category="support",
                subject=f"Re: {subject}",
                body=reply_text,
                thread_id=thread_id,
                message_id=message_id,
                intent=intent,
                channel="email"
            )
            logger.info(f"email - saved reply history for {customer_email}")
            
            # For appointment intents: generate and send booking confirmation with .ics
            if intent == "appointment" and booking_info_pending:
                booking_info = self.appointment_workflow.handle_booking_request(
                    customer_email=booking_info_pending["customer_email"],
                    message_text=booking_info_pending["message_text"],
                    thread_id=booking_info_pending["thread_id"],
                    message_id=booking_info_pending["message_id"],
                    subject=booking_info_pending["subject"],
                    selected_slot=booking_info_pending["selected_slot"],
                    reply_text=booking_info_pending["reply_text"]
                )
                
                if booking_info and booking_info.get("status") == "confirmed":
                    booking_response = BookingResponseSchema(
                        id=booking_info["id"],
                        slot=booking_info["slot"],
                        customer_email=booking_info["customer_email"],
                        channel=booking_info["channel"],
                        status=booking_info["status"],
                        booked_at=booking_info["booked_at"],
                        notes=booking_info.get("notes")
                    )
                    booking_confirmation_sent = booking_info.get("confirmation_sent", False)
            
            # For cancellation intents: find and cancel existing booking
            elif intent == "cancellation" and booking_info_pending:
                cancellation_result = self.appointment_workflow.handle_cancellation_request(
                    customer_email=booking_info_pending["customer_email"],
                    email_text=booking_info_pending["message_text"],
                    reply_text=booking_info_pending["reply_text"],
                    thread_id=booking_info_pending["thread_id"],
                    message_id=booking_info_pending["message_id"],
                    references=booking_info_pending.get("references", ""),
                    subject=booking_info_pending["subject"]
                )
                
                if cancellation_result and cancellation_result.get("status") == "success":
                    logger.info(f"email - cancellation processed successfully for {booking_info_pending['customer_email']}")
                    # Mark that confirmation email was already sent
                    booking_confirmation_sent = True
            
            # For rescheduling intents: find existing booking and propose new slot
            elif intent == "rescheduling" and booking_info_pending:
                rescheduling_result = self.appointment_workflow.handle_rescheduling_request(
                    customer_email=booking_info_pending["customer_email"],
                    email_text=booking_info_pending["message_text"],
                    reply_text=booking_info_pending["reply_text"],
                    thread_id=booking_info_pending["thread_id"],
                    message_id=booking_info_pending["message_id"],
                    subject=booking_info_pending["subject"],
                    selected_slot=booking_info_pending.get("selected_slot")
                )
                
                if rescheduling_result and rescheduling_result.get("status") == "success":
                    logger.info(f"email - rescheduling processed successfully for {booking_info_pending['customer_email']}")
                    # Mark that confirmation email with .ics was already sent
                    booking_confirmation_sent = True
                elif rescheduling_result and rescheduling_result.get("message") == "No active appointment found to reschedule":
                    # Fallback: if rescheduling intent was misclassified and no active booking exists,
                    # treat it as a new appointment request and create booking
                    logger.warning(f"email - rescheduling failed (no active booking), falling back to create new appointment for {booking_info_pending['customer_email']}")
                    
                    booking_info = self.appointment_workflow.handle_booking_request(
                        customer_email=booking_info_pending["customer_email"],
                        message_text=booking_info_pending["message_text"],
                        thread_id=booking_info_pending["thread_id"],
                        message_id=booking_info_pending["message_id"],
                        subject=booking_info_pending["subject"],
                        selected_slot=booking_info_pending["selected_slot"],
                        reply_text=booking_info_pending["reply_text"]
                    )
                    
                    if booking_info and booking_info.get("status") == "confirmed":
                        booking_response = BookingResponseSchema(
                            id=booking_info["id"],
                            slot=booking_info["slot"],
                            customer_email=booking_info["customer_email"],
                            channel=booking_info["channel"],
                            status=booking_info["status"],
                            booked_at=booking_info["booked_at"],
                            notes=booking_info.get("notes")
                        )
                        booking_confirmation_sent = booking_info.get("confirmation_sent", False)
            
            logger.info(f"email - auto-sending response (urgency: {urgency_level})", extra={"channel": "email"})
            return ChannelMessageResponseSchema(
                channel="email",
                status=MessageStatus.AUTO_SEND,
                intent=_intent_to_enum(intent),
                reply=reply_text,
                booking=booking_response,
                retrieved_docs=retrieved_docs,
                error_code=None,
                error_message=None,
                metadata={
                    "urgency_level": urgency_level,
                    "urgency_confidence": urgency_confidence,
                    "booking_confirmation_sent": booking_confirmation_sent
                }
            )

# Module-level convenience function for backward compatibility
_email_agent = None


def get_email_agent():
    """
    Get or create the global EmailAgent instance.
    Uses lazy initialization to ensure database is ready first.
    """
    global _email_agent
    if _email_agent is None:
        _email_agent = EmailAgent()
    return _email_agent


def process_email(email_payload: dict) -> ChannelMessageResponseSchema:
    """
    Convenience function to process emails.
    Maintains backward compatibility with existing code that calls
    process_email() directly.
    """
    agent = get_email_agent()
    return agent.process_email(email_payload)

