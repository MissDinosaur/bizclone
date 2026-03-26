import logging
from channels.email.parser import parse_email
from channels.email.intent_classifier import IntentClassifier
from channels.email.urgency_detector import UrgencyDetector
from rag.rag_pipeline import EmailRAGPipeline
from scheduling.scheduler import check_availability, book_slot
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
    
    Note: Intent (what user wants) and Urgency (time-sensitivity) are
    detected separately for better decision-making.
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

        # Step 1: Save incoming email to history
        self.email_store.save_email(
            customer_email=customer_email,
            sender_category="customer",
            subject=subject,
            body=email_text,
            our_reply=None,  # Will add this later
            intent=None,  # Will set after detection
            channel="email"
        )

        # Step 2: Intent Detection (NLP) - SEPARATE from urgency
        intent_result = self.intent_model.predict_intent(email_text)
        intent = intent_result["intent"]
        intent_confidence = intent_result["confidence"]
        logger.info(f"email - intent: {intent} ({intent_confidence:.0%})", extra={"channel": "email"})
        
        # Step 2b: Urgency Detection (keyword-based) - INDEPENDENT of intent
        urgency_result = self.urgency_detector.detect_urgency(email_text, intent=intent)
        urgency_level = urgency_result["urgency_level"]
        urgency_confidence = urgency_result["confidence"]
        escalation_reason = urgency_result["escalation_reason"]
        detected_keywords = urgency_result["detected_keywords"]
        
        logger.info(f"email - urgency: {urgency_level} ({urgency_confidence:.0%}) - {escalation_reason}", extra={"channel": "email"})
        if detected_keywords:
            logger.warning(f"email - escalation keywords: {detected_keywords}", extra={"channel": "email"})
        
        # Step 3: Scheduling Logic (Optional)
        booking_info = None
        booking_response = None
        if intent == cfg.APPOINTMENT:
            booking_info = self._handle_booking_request(customer_email, email_text)
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

        # Step 4: RAG + LLM Email Draft
        reply_text, retrieved_docs = self.rag.generate_email_reply(
            customer_email=customer_email,
            body=email_text,
            intent=intent,
            booking=booking_info
        )
        
        # Step 5: Save the generated reply to history (for outgoing emails)
        self.email_store.save_email(
            customer_email=customer_email,
            sender_category="support",
            subject=f"Re: {subject}",
            body=reply_text,
            our_reply=reply_text,
            intent=intent,
            channel="email"
        )
        logger.debug(f"email - saved reply history for {customer_email}")
        
        # Step 6: DECISION LOGIC - Based on URGENCY
        # Urgency determines escalation, intent determines reply content
        should_escalate = self.urgency_detector.should_escalate_to_owner(urgency_level)
        
        if should_escalate:
            logger.warning(f"email - [{urgency_level}] escalating to owner from {customer_email}", extra={"channel": "email"})
            logger.warning(f"email - reason: {escalation_reason}", extra={"channel": "email"})
            return ChannelMessageResponseSchema(
                channel="email",
                status=MessageStatus.NEEDS_REVIEW,
                intent=_intent_to_enum(intent),
                reply=reply_text,
                booking=booking_response,
                retrieved_docs=retrieved_docs,
                error_code=None,
                error_message=None,
                # NEW: Store urgency info for owner review context
                metadata={
                    "urgency_level": urgency_level,
                    "urgency_confidence": urgency_confidence,
                    "escalation_reason": escalation_reason,
                    "detected_keywords": detected_keywords,
                    "intent_confidence": intent_confidence
                }
            )
        
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
                "urgency_confidence": urgency_confidence
            }
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
        
        # Try to book the first available slot and save the booking info to the database
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

