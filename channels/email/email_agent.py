import logging
import json
from channels.email.parser import parse_email
from channels.email.intent_classifier import IntentClassifier
from channels.email.review_store import add_email_to_review
from channels.email.urgency_detector import UrgencyDetector
from rag.rag_pipeline import EmailRAGPipeline
from scheduling.scheduler import check_availability, book_slot
from scheduling.llm_booking_assistant import get_booking_assistant
from channels.email.booking_email_sender import get_booking_email_sender
from knowledge_base.email_history_store import EmailHistoryStore
from channels.schemas import ChannelMessageResponseSchema, IntentType, MessageStatus, BookingResponseSchema
import config.config as cfg

logger = logging.getLogger(__name__)

""" Email Agent Orchestrator (End-to-End Brain) """


def _intent_to_enum(intent_str: str) -> IntentType:
    """
    Convert intent string (15 new categories) to IntentType enum.
    Note: EMERGENCY is no longer an intent - it's now detected as urgency level.
    Maps new 15-category intents to IntentType enum values (also 15 values now).
    """
    intent_mapping = {        
        # New 15-category intent labels → IntentType enum (15 values)
        # Query intents
        "price_inquiry": IntentType.PRICING_INQUIRY,
        "payment_inquiry": IntentType.PAYMENT_INQUIRY,
        "working_hours": IntentType.WORKING_HOURS,
        "upgrade_inquiry": IntentType.UPGRADE_INQUIRY,
        
        # Action intents
        "appointment": IntentType.APPOINTMENT,
        "cancellation": IntentType.CANCELLATION,
        "service_request": IntentType.SERVICE_REQUEST,
        "bulk_inquiry": IntentType.BULK_INQUIRY,
        
        # Feedback intents
        "complaint": IntentType.COMPLAINT,
        "feedback": IntentType.FEEDBACK,
        "warranty_claim": IntentType.WARRANTY_CLAIM,
        "replacement_request": IntentType.REPLACEMENT_REQUEST,
        
        # Financial intents
        "refund_request": IntentType.REFUND_REQUEST,
        
        # Fallback
        "faq": IntentType.FAQ,
        "other": IntentType.OTHER,
    }
    
    return intent_mapping.get(intent_str, IntentType.FAQ)  # Default to FAQ if unknown


class EmailAgent:
    """
    Email message processor.
    Handles the end-to-end email pipeline:
    1. Parse incoming email
    2. Predict intent using NLP model (15 categories)
    3. Detect urgency level (CRITICAL/HIGH/NORMAL) - INDEPENDENT of intent
    4. Retrieve relevant KB context (RAG)
    5. Generate final reply draft using LLM
    6. Optionally handle scheduling requests
    """

    def __init__(self):
        self.rag = EmailRAGPipeline()
        self.intent_model = IntentClassifier()
        self.urgency_detector = UrgencyDetector()
        self.email_store = EmailHistoryStore()

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
        in_reply_to = email_payload.get("in_reply_to", "")  # Extract reply context
        
        logger.info(f"[CONVERSATION_CHAIN] message_id='{message_id}', references='{references}')")

        # Step 2: Save incoming email to history
        self.email_store.save_email(
            customer_email=customer_email,
            sender_category="customer",
            subject=subject,
            body=email_text,
            thread_id=thread_id,
            message_id=message_id,
            intent=None,  # Will set after detection
            channel="email"
        )

        # Step 3: Intent Detection (NLP) - SEPARATE from urgency
        intent_result = self.intent_model.predict_intent(email_text)
        intent = intent_result["intent"]
        intent_confidence = intent_result["confidence"]
        logger.info(f"email - intent: {intent} ({intent_confidence:.0%})", extra={"channel": "email"})
        
        # Step 4: Urgency Detection (keyword-based) - INDEPENDENT of intent
        urgency_result = self.urgency_detector.detect_urgency(email_text, intent=intent)
        urgency_level = urgency_result["urgency_level"]
        urgency_confidence = urgency_result["confidence"]
        escalation_reason = urgency_result["escalation_reason"]
        detected_keywords = urgency_result["detected_keywords"]
        
        logger.info(f"email - urgency: {urgency_level} ({urgency_confidence:.0%}) - {escalation_reason}", extra={"channel": "email"})
        if detected_keywords:
            logger.warning(f"email - escalation keywords: {detected_keywords}", extra={"channel": "email"})
        
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
            
            slot_selection_result = self._select_best_appointment_slot(
                customer_email=customer_email,
                email_text=email_text
            )
            
            if slot_selection_result:
                logger.warning("Select appointment slot, generating standard reply")
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
            # Final reply will be saved AFTER owner approval (Step 7b in review_email_ui.py)
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
                "booking_pending": json.dumps(booking_info_pending) if booking_info_pending else None,  # Convert dict to JSON string
                "selected_slot": selected_slot  # For owner to modify if appointment
            }
            logger.debug(f"DEBUG: Adding to review queue - customer_email='{customer_email}' (type={type(customer_email).__name__})")
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
            logger.debug(f"email - saved reply history for {customer_email}")
            
            # For appointment intents: generate and send booking confirmation with .ics
            if intent == "appointment" and booking_info_pending:
                booking_info = self._handle_booking_request(
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

    def _select_best_appointment_slot(
        self,
        customer_email: str,
        email_text: str
    ) -> dict:
        """
        Select the best available appointment slot for a customer.
        This is called BEFORE generating the LLM reply, so the reply
        can be generated with knowledge of the selected slot.
        
        Args:
            customer_email: Customer's email address
            email_text: Content of customer's email
            
        Returns:
            dict with 'slot' and 'reasoning', or None if no slot available
        """
        try:
            # Get available time slots
            available_slots = check_availability(days_ahead=14)
            
            if not available_slots:
                logger.warning(f"email - no available slots for {customer_email}")
                return None
            
            # Use LLM to intelligently select the best slot
            booking_assistant = get_booking_assistant()
            selected_slot, llm_reasoning = booking_assistant.select_best_appointment_slot(
                customer_email=customer_email,
                email_content=email_text,
                available_slots=available_slots
            )
            
            if not selected_slot:
                logger.warning(f"email - LLM failed to select slot for {customer_email}")
                return None
            
            logger.info(f"email - selected slot: {selected_slot} - Reasoning: {llm_reasoning}")
            
            return {
                "slot": selected_slot,
                "reasoning": llm_reasoning
            }
            
        except Exception as e:
            logger.error(f"Error in _select_best_appointment_slot: {e}", exc_info=True)
            return None

    def _handle_booking_request(
        self,
        customer_email: str,
        message_text: str,
        thread_id: str,
        message_id: str,
        subject: str,
        selected_slot: str,
        reply_text: str
    ) -> dict:
        """
        Complete the booking workflow with an already-selected slot.
        This is called AFTER slot selection and reply generation.
        
        Flow:
        1. Create booking record with the selected slot
        2. Generate iCalendar invitation
        3. Send confirmation email with reply_text + .ics attachment in same thread
        
        Args:
            customer_email: Customer's email address
            message_text: Original customer email content
            thread_id: Gmail thread ID for threaded reply
            message_id: Gmail message ID for reply-to reference
            subject: Original email subject
            selected_slot: Already-selected appointment slot
            reply_text: LLM-generated reply (with slot context already included)
            
        Returns:
            dict with booking info + confirmation_sent flag
        """
        
        try:
            # Step 1: Create booking record with the already-selected slot
            booking = book_slot(
                customer_email=customer_email,
                slot=selected_slot,
                channel="email",
                notes=f"AI-selected booking from email: {message_text[:100]}",
                days_ahead=14
            )
            
            if booking.get("status") != "confirmed":
                logger.warning(f"email - booking creation failed for {customer_email}: {booking.get('reason')}")
                return None
            
            logger.info(f"email - booking confirmed: {booking.get('id')} for {customer_email} at {selected_slot}")
            
            # Step 2: Send confirmation email with iCalendar invitation AND LLM reply
            email_sender = get_booking_email_sender()
            customer_name = customer_email.split('@')[0]  # Extract customer name from email
            
            # Append booking details to the reply (which already includes slot context)
            email_body = f"""{reply_text}

---
Appointment Details:
Time: {selected_slot}
Status: Confirmed

To reschedule, please reply directly to this email."""
            
            # send_booking_confirmation_with_ics now receives:
            # - reply_text with slot context already included
            # - selected_slot for iCalendar generation
            success, message_id = email_sender.send_booking_confirmation_with_ics(
                customer_email=customer_email,
                customer_name=customer_name,
                appointment_slot=selected_slot,
                thread_id=thread_id,
                message_id=message_id,
                service_description="Consultation Booking",
                service_duration_minutes=60,
                email_body=email_body,
                subject=f"Re: {subject}"
            )
            
            if success:
                logger.info(f"email - booking confirmation sent to {customer_email}")
                booking["message_id"] = message_id
                booking["confirmation_sent"] = True
            else:
                logger.warning(f"email - failed to send booking confirmation: {message_id}")
                booking["confirmation_sent"] = False
            
            return booking
            
        except Exception as e:
            logger.error(f"Error in _handle_booking_request: {e}", exc_info=True)
            return None


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

