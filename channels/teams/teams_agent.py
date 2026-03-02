"""
Teams Channel Agent

Processes Teams messages and handles scheduling using the shared scheduler.
Template for implementing agents in other channels.
"""
from scheduling.scheduler import check_availability, book_slot


class TeamsAgent:
    """
    Teams message processor.
    Demonstrates how to use the centralized scheduling service
    in any input channel.
    """

    def __init__(self):
        pass

    def process_message(self, message: dict):
        """
        Process a Teams message.
        Args:
            message: Message dict with keys: from, text, thread_id, etc. 
        Returns:
            Processed response dict
        """
        sender = message.get("from")
        text = message.get("text", "")
        
        print(f"[TEAMS] Processing message from {sender}")
        
        # TODO: Add intent classification for Teams messages
        # intent = intent_classifier.predict_intent(text)
        
        # Example: Handle appointment booking intent
        booking = None
        if "book" in text.lower() or "appointment" in text.lower():
            booking = self._handle_booking_request(sender, text)
        
        # TODO: Add RAG pipeline for Teams context retrieval
        # reply_text = rag.generate_reply(text, intent)
        
        return {
            "channel": "teams",
            "status": "auto_send",
            "sender": sender,
            "booking": booking,
            "reply": "Message processed (template response)"
        }

    def _handle_booking_request(self, user_email: str, message_text: str) -> dict:
        """
        Handle appointment booking request from Teams.
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
            customer_email=user_email,
            slot=selected_slot,
            channel="teams",
            notes=f"Teams message: {message_text[:100]}"
        )
        
        return booking


def process_teams_message(message: dict):
    """
    Convenience function to process Teams messages.
    Can be called from the TeamsWatcher.
    """
    agent = TeamsAgent()
    return agent.process_message(message)
