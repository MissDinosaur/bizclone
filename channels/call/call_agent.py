"""
Call Channel Agent

Processes incoming call requests and handles scheduling using the shared scheduler.
Template for implementing agents in other channels.
"""
from scheduling.scheduler import check_availability, book_slot


class CallAgent:
    """
    Call processor.
    Demonstrates how to use the centralized scheduling service
    for incoming call requests (e.g., missed calls, voicemails).
    """

    def __init__(self):
        pass

    def process_call(self, call_data: dict):
        """
        Process a call or voicemail.
        Args:
            call_data: Call dict with keys: from, transcription, call_id, etc.   
        Returns:
            Processed response dict
        """
        caller = call_data.get("from")
        transcription = call_data.get("transcription", "No transcription available")
        
        print(f"[CALL] Processing call from {caller}")
        
        # TODO: Add intent classification for call transcriptions
        # intent = intent_classifier.predict_intent(transcription)
        
        # Example: Handle appointment booking intent
        booking = None
        if "book" in transcription.lower() or "appointment" in transcription.lower():
            booking = self._handle_booking_request(caller, transcription)
        
        # TODO: Add text-to-speech for call callback response
        # reply_text = rag.generate_reply(transcription, intent)
        
        return {
            "channel": "call",
            "status": "pending_callback",
            "caller": caller,
            "booking": booking,
            "callback_message": "We received your call and will process your request"
        }

    def _handle_booking_request(self, caller_phone: str, transcription: str) -> dict:
        """
        Handle appointment booking request from call.
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
            customer_email=caller_phone,  # Store phone as identifier
            slot=selected_slot,
            channel="call",
            notes=f"Call transcription: {transcription[:100]}"
        )
        
        return booking


def process_call(call_data: dict):
    """
    Convenience function to process calls.
    Can be called from the CallWatcher.
    """
    agent = CallAgent()
    return agent.process_call(call_data)
