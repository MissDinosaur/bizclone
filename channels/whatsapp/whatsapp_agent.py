"""
WhatsApp Channel Agent

Processes WhatsApp messages and handles scheduling using the shared scheduler.
Template for implementing agents in other channels.
"""
from scheduling.scheduler import check_availability, book_slot


class WhatsAppAgent:
    """
    WhatsApp message processor.
    Demonstrates how to use the centralized scheduling service
    in any input channel.
    """

    def __init__(self):
        pass

    def process_message(self, message: dict):
        """
        Process a WhatsApp message.
        Args:
            message: Message dict with keys: from, text, message_id, etc. 
        Returns:
            Processed response dict
        """
        sender = message.get("from")
        text = message.get("text", "")
        
        print(f"[WHATSAPP] Processing message from {sender}")
        
        # TODO: Add intent classification for WhatsApp messages
        # intent = intent_classifier.predict_intent(text)
        
        # Example: Handle appointment booking intent
        booking = None
        if "book" in text.lower() or "appointment" in text.lower():
            booking = self._handle_booking_request(sender, text)
        
        # TODO: Add RAG pipeline for WhatsApp context retrieval
        # reply_text = rag.generate_reply(text, intent)
        
        return {
            "channel": "whatsapp",
            "status": "auto_send",
            "sender": sender,
            "booking": booking,
            "reply": "Message processed (template response)"
        }

    def _handle_booking_request(self, user_phone: str, message_text: str) -> dict:
        """
        Handle appointment booking request from WhatsApp.
        Uses the shared scheduling service so bookings are consistent
        across all channels.
        """
        available_slots = check_availability(days_ahead=7)
        
        if not available_slots:
            return {
                "status": "failed",
                "reason": "No available slots"
            }
        
        # Book the first available slot
        selected_slot = available_slots[0]
        booking = book_slot(
            customer_email=user_phone,  # Store phone as identifier
            slot=selected_slot,
            channel="whatsapp",
            notes=f"WhatsApp message: {message_text[:100]}"
        )
        
        return booking


def process_whatsapp_message(message: dict):
    """
    Convenience function to process WhatsApp messages.
    Can be called from the WhatsAppWatcher.
    """
    agent = WhatsAppAgent()
    return agent.process_message(message)
