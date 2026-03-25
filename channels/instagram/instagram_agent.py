"""
channels/instagram/instagram_agent.py

Processes incoming Instagram DMs through the shared BizClone
agent pipeline (IntentClassifier → RAG → Scheduler) and always
returns a ChannelMessageResponseSchema.
"""

import logging
from channels.schemas import (
    ChannelMessageResponseSchema,
    IntentType,
    MessageStatus,
)
from channels.email.intent_classifier import IntentClassifier
from rag.rag_pipeline import EmailRAGPipeline
from scheduling.scheduler import check_availability, book_slot
import config.config as cfg

logger = logging.getLogger(__name__)


class InstagramAgent:
    """Process Instagram DMs through the shared agent pipeline."""

    def __init__(self):
        self.intent_model = IntentClassifier()
        self.rag = EmailRAGPipeline()

    def process_message(self, message: dict) -> ChannelMessageResponseSchema:
        sender_id = message.get("from", "unknown")
        text = message.get("body", "")

        try:
            intent_str = self.intent_model.classify(text)
            intent = self._intent_to_enum(intent_str)
            logger.info(f"Instagram [{sender_id}]: intent={intent_str}")

            if intent == IntentType.APPOINTMENT:
                booking_result = self._handle_booking_request(sender_id, text)
                reply = booking_result.get("reply", "I'll check availability and get back to you!")
                return ChannelMessageResponseSchema(
                    channel="instagram",
                    status=MessageStatus.AUTO_SEND,
                    intent=intent.value,
                    reply=reply,
                    booking=booking_result.get("booking"),
                )

            rag_result = self.rag.query(text)
            reply = rag_result.get("answer", "Thanks for your message! We'll get back to you shortly. 🙏")
            retrieved_docs = rag_result.get("source_documents", [])

            return ChannelMessageResponseSchema(
                channel="instagram",
                status=MessageStatus.AUTO_SEND,
                intent=intent.value,
                reply=reply,
                retrieved_docs=[doc.metadata.get("source", "") for doc in retrieved_docs],
            )

        except Exception as exc:
            logger.error(f"Instagram [{sender_id}]: agent pipeline failed — {exc}")
            return ChannelMessageResponseSchema(
                channel="instagram",
                status=MessageStatus.FAILED,
                intent=IntentType.FAQ.value,
                reply="Thanks for your message! We'll get back to you shortly. 🙏",
                error_code="AGENT_ERROR",
                error_message=str(exc),
            )

    def _handle_booking_request(self, sender_id: str, text: str) -> dict:
        try:
            available_slots = check_availability()
            if not available_slots:
                return {"reply": "Sorry, no slots are available right now. Please try again later."}

            slot = available_slots[0]
            booking = book_slot(
                customer_email=sender_id,
                slot=slot,
                channel="instagram",
                notes="Booked via Instagram DM",
            )
            return {
                "reply": f"Your appointment is booked for {slot}! 🎉 We'll see you then.",
                "booking": booking,
            }
        except Exception as exc:
            logger.error(f"Instagram: booking failed for {sender_id} — {exc}")
            return {"reply": "I couldn't complete the booking right now. Please contact us directly."}

    def _intent_to_enum(self, intent_str: str) -> IntentType:
        intent_mapping = {
            cfg.PRICE_INQUERY: IntentType.PRICING_INQUIRY,
            cfg.APPOINTMENT: IntentType.APPOINTMENT,
            cfg.CANCELLATION: IntentType.CANCELLATION,
            cfg.WORKING_HOUR: IntentType.WORKING_HOURS,
            cfg.EMERGENCY: IntentType.EMERGENCY,
            cfg.FAQ: IntentType.FAQ,
        }
        return intent_mapping.get(intent_str, IntentType.FAQ)


_instagram_agent = InstagramAgent()


def process_message(message: dict) -> ChannelMessageResponseSchema:
    return _instagram_agent.process_message(message)
