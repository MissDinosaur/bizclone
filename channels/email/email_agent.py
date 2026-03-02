import logging
from channels.email.parser import parse_email
from channels.email.intent_classifier import IntentClassifier
from rag.rag_pipeline import EmailRAGPipeline
from scheduling.scheduler import check_availability, book_slot
from channels.schemas import ChannelMessageResponseSchema, IntentType, MessageStatus, BookingResponseSchema
import config.config as cfg

logger = logging.getLogger(__name__)

""" Email Agent Orchestrator (End-to-End Brain) """


def _intent_to_enum(intent_str: str) -> IntentType:
    """
    Convert intent string to IntentType enum.
    Handles mapping from config constants to enum values.
    """
    intent_mapping = {
        cfg.PRICE_INQUERY: IntentType.PRICING_INQUIRY,
        cfg.APPOINTMENT: IntentType.APPOINTMENT,
        cfg.CANCELLATION: IntentType.CANCELLATION,
        cfg.WORKING_HOUR: IntentType.WORKING_HOURS,
        cfg.EMERGENCY: IntentType.EMERGENCY,
        cfg.FAQ: IntentType.FAQ,
    }
    
    return intent_mapping.get(intent_str, IntentType.FAQ)  # Default to FAQ if unknown


class EmailAgent:
    """
    Email message processor.
    Handles the end-to-end email pipeline:
    1. Parse incoming email
    2. Predict intent using NLP model
    3. Retrieve relevant KB context (RAG)
    4. Generate final reply draft using LLM
    5. Optionally handle scheduling requests
    """

    def __init__(self):
        self.rag = EmailRAGPipeline()
        self.intent_model = IntentClassifier()

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
        text = parsed["text"]

        # Step 2: Intent Detection (NLP)
        intent_result = self.intent_model.predict_intent(text)
        intent = intent_result["intent"]
        logger.info(f"email - intent detected: {intent}", extra={"channel": "email"})
        
        # Step 3: Scheduling Logic (Optional)
        booking = None
        booking_response = None
        if intent == cfg.APPOINTMENT:
            booking = self._handle_booking_request(email_payload["from"], text)
            if booking and booking.get("status") == "confirmed":
                booking_response = BookingResponseSchema(
                    id=booking["id"],
                    slot=booking["slot"],
                    customer_email=booking["customer_email"],
                    channel=booking["channel"],
                    status=booking["status"],
                    booked_at=booking["booked_at"],
                    notes=booking.get("notes")
                )

        # Step 4: RAG + LLM Email Draft
        reply_text, retrieved_docs = self.rag.generate_email_reply(
            customer_email=text,
            intent=intent,
            booking=booking
        )
        
        # Emergency emails require owner review
        if intent == cfg.EMERGENCY:
            logger.warning(f"email - emergency detected from {email_payload['from']}", extra={"channel": "email"})
            return ChannelMessageResponseSchema(
                channel="email",
                status=MessageStatus.NEEDS_REVIEW,
                intent=_intent_to_enum(intent),
                reply=reply_text,
                booking=booking_response,
                retrieved_docs=retrieved_docs,
                error_code=None,
                error_message=None
            )
        
        logger.info(f"email - auto-send response", extra={"channel": "email"})
        return ChannelMessageResponseSchema(
            channel="email",
            status=MessageStatus.AUTO_SEND,
            intent=_intent_to_enum(intent),
            reply=reply_text,
            booking=booking_response,
            retrieved_docs=retrieved_docs,
            error_code=None,
            error_message=None
        )

    def _handle_booking_request(self, customer_email: str, message_text: str) -> dict:
        """
        Handle appointment booking request from email.
        Uses the shared scheduling service so bookings are consistent
        across all channels.
        """
        available_slots = check_availability(days_ahead=5)
        
        if not available_slots:
            logger.warning(f"email - no available slots for booking from {customer_email}")
            return None
        
        # Try to book the first available slot
        selected_slot = available_slots[0]
        booking = book_slot(
            customer_email=customer_email,
            slot=selected_slot,
            channel="email",
            notes=f"Requested via email: {message_text[:100]}"
        )
        
        if booking.get("status") == "failed":
            logger.warning(f"email - booking failed for {customer_email}: {booking.get('reason')}")
            return None
        else:
            logger.info(f"email - booking confirmed: {booking.get('id')} for {customer_email}")
            return booking


# Module-level convenience function for backward compatibility
_email_agent = EmailAgent()


def process_email(email_payload: dict) -> ChannelMessageResponseSchema:
    """
    Convenience function to process emails.
    Maintains backward compatibility with existing code that calls
    process_email() directly.
    """
    return _email_agent.process_email(email_payload)

