"""
Facebook Channel Agent

Processes Facebook messages and page comments, handles scheduling using the shared scheduler.
Template for implementing agents in other channels.
"""
from scheduling.scheduler import check_availability, book_slot


class FacebookAgent:
    """
    Facebook message processor.
    Demonstrates how to use the centralized scheduling service
    for Facebook messages and page comments.
    """

    def __init__(self):
        pass

    def process_message(self, message: dict):
        """
        Process a Facebook message or comment.
        Args:
            message: Message dict with keys: from, text, message_id, is_comment, etc.   
        Returns:
            Processed response dict
        """
        sender = message.get("from")
        text = message.get("text", "")
        is_comment = message.get("is_comment", False)
        msg_type = "comment" if is_comment else "message"
        
        print(f"[FACEBOOK] Processing {msg_type} from {sender}")
        
        # TODO: Add intent classification for Facebook messages
        # intent = intent_classifier.predict_intent(text)
        
        # Example: Handle appointment booking intent
        booking = None
        if "book" in text.lower() or "appointment" in text.lower():
            booking = self._handle_booking_request(sender, text)
        
        # TODO: Add RAG pipeline for Facebook context retrieval
        # reply_text = rag.generate_reply(text, intent)
        
        return {
            "channel": "facebook",
            "status": "auto_send",
            "message_type": msg_type,
            "sender": sender,
            "booking": booking,
            "reply": "Message processed (template response)"
        }

    def _handle_booking_request(self, user_facebook_id: str, message_text: str) -> dict:
        """
        Handle appointment booking request from Facebook.
        
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
            customer_email=user_facebook_id,  # Store Facebook ID as identifier
            slot=selected_slot,
            channel="facebook",
            notes=f"Facebook message: {message_text[:100]}"
        )
        
        return booking


def process_facebook_message(message: dict):
    """
    Convenience function to process Facebook messages.
    Can be called from the FacebookWatcher.
    """
    agent = FacebookAgent()
    return agent.process_message(message)
