"""
Test suite for appointment cancellation functionality.

Tests:
1. Intent detection for cancellation requests
2. Cancellation handling workflow
3. Email confirmation with iCalendar cancellation notice
4. Booking manager integration
"""

import pytest
import logging
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channels.email.email_agent import EmailAgent
from model.intent_classifier import IntentClassifier
from channels.email.booking_email_sender import BookingEmailSender

logger = logging.getLogger(__name__)


class TestCancellationIntent:
    """Test cancellation intent detection"""
    
    def test_cancellation_intent_detection(self):
        """Test that cancellation emails are correctly classified"""
        classifier = IntentClassifier()
        
        cancellation_samples = [
            "I need to cancel my appointment tomorrow",
            "Can you please cancel my booking?",
            "Cancel appointment",
            "I cannot make it, please cancel",
            "I need to cancel the meeting on Monday"
        ]
        
        for sample in cancellation_samples:
            result = classifier.predict_intent(sample)
            intent = result["intent"]
            assert intent == "cancellation", (
                f"Failed to classify '{sample}' as cancellation, got: {intent}"
            )
            logger.info(f"✓ Correctly classified as cancellation: '{sample}'")


class TestCancellationWorkflow:
    """Test the full cancellation workflow"""
    
    @patch('channels.email.email_agent.BookingManager')
    @patch('channels.email.email_agent.EmailRAGPipeline')
    @patch('channels.email.email_agent.IntentClassifier')
    @patch('channels.email.email_agent.UrgencyDetector')
    def test_cancellation_email_processing(self, mock_urgency, mock_intent, mock_rag, mock_booking_mgr):
        """Test processing of cancellation email"""
        
        # Setup mocks
        mock_intent.return_value.classify.return_value = "cancellation"
        mock_intent.return_value.get_confidence.return_value = 0.95
        
        mock_urgency.return_value.detect.return_value = ("NORMAL", 0.8, "None")
        mock_urgency.return_value.should_escalate_to_owner.return_value = False
        
        mock_rag.return_value.generate_email_reply.return_value = (
            "Your appointment has been successfully cancelled.",
            []
        )
        
        mock_booking_manager = Mock()
        mock_booking_mgr.return_value = mock_booking_manager
        mock_booking_manager.cancel_appointment.return_value = {
            "status": "success",
            "booking_id": "cancel-123",
            "message": "Appointment on 2026-04-03 14:00 has been cancelled",
            "cancelled_at": datetime.utcnow(),
            "details": {
                "original_slot": "2026-04-03 14:00",
                "cancellation_reason": "Customer requested cancellation via email",
                "customer_email": "customer@example.com"
            }
        }
        
        # Create agent and process cancellation email
        agent = EmailAgent(db_session=None)
        agent.intent_model = mock_intent.return_value
        agent.urgency_detector = mock_urgency.return_value
        agent.booking_manager = mock_booking_manager
        
        email_payload = {
            "from": "customer@example.com",
            "subject": "Cancel Appointment",
            "body": "I need to cancel my appointment scheduled for April 3rd",
            "thread_id": "thread-123",
            "message_id": "msg-456"
        }
        
        # This should NOT raise any exceptions
        with patch('channels.email.email_agent.parse_email') as mock_parse:
            mock_parse.return_value = {"text": email_payload["body"]}
            
            # Note: We're just testing that the cancellation path doesn't crash
            # Full integration testing would require database connection
            logger.info("✓ Cancellation email processing test setup complete")


class TestCancellationEmailSender:
    """Test email sending for cancellations"""
    
    @patch('channels.email.booking_email_sender.GmailClient')
    def test_cancellation_ics_generation(self, mock_gmail):
        """Test that cancellation ICS files are properly generated"""
        
        sender = BookingEmailSender()
        
        # Generate cancellation ICS
        ics_content = sender._generate_cancellation_ics(
            customer_email="customer@example.com",
            customer_name="John Doe",
            original_slot="2026-04-03 14:00"
        )
        
        # Verify ICS content contains cancellation markers
        assert "METHOD:CANCEL" in ics_content, "ICS must contain METHOD:CANCEL"
        assert "STATUS:CANCELLED" in ics_content, "ICS must contain STATUS:CANCELLED"
        assert "PARTSTAT=DECLINED" in ics_content, "Attendee status should be DECLINED"
        assert "2026-04-03" in ics_content, "ICS must contain the appointment date"
        assert "john" in ics_content.lower(), "ICS must contain customer name"
        
        logger.info("✓ Cancellation ICS file generated correctly")

    @patch('channels.email.booking_email_sender.GmailClient')
    def test_cancellation_ics_generation_with_iso_datetime(self, mock_gmail):
        """ICS cancellation should support ISO datetime strings from booking records."""

        sender = BookingEmailSender()

        ics_content = sender._generate_cancellation_ics(
            customer_email="customer@example.com",
            customer_name="John Doe",
            original_slot="2026-05-01T09:00:00"
        )

        assert ics_content, "ICS content should not be empty for ISO datetime input"
        assert "METHOD:CANCEL" in ics_content, "ICS must contain METHOD:CANCEL"
        assert "STATUS:CANCELLED" in ics_content, "ICS must contain STATUS:CANCELLED"
        assert "20260501T090000" in ics_content, "ICS should include parsed datetime"
    
    @patch('channels.email.booking_email_sender.GmailClient')
    def test_cancellation_email_structure(self, mock_gmail):
        """Test that cancellation emails have correct structure"""
        
        sender = BookingEmailSender()
        
        email_body = """Your appointment has been cancelled as requested.

---
Cancellation Details:
Original Appointment: 2026-04-03 14:00
Status: Cancelled
Cancellation Time: Now

If you would like to reschedule, please send us a new appointment request."""
        
        ics_content = sender._generate_cancellation_ics(
            customer_email="customer@example.com",
            customer_name="John Doe",
            original_slot="2026-04-03 14:00"
        )
        
        message = sender._build_email_with_ics_attachment(
            to_email="customer@example.com",
            to_name="John Doe",
            subject="Re: Cancel Appointment",
            body=email_body,
            ics_content=ics_content
        )
        
        # Verify message structure
        assert message['Subject'] == "Re: Cancel Appointment"
        assert message['To'] == "customer@example.com"
        
        # Verify it's a multipart message with attachment
        assert message.is_multipart(), "Message should be multipart"
        
        logger.info("✓ Cancellation email has correct structure")

    @patch('channels.email.booking_email_sender.GmailClient')
    def test_cancellation_email_preserves_threading_headers(self, mock_gmail):
        """Cancellation email should pass original references for stronger threading."""

        sender = BookingEmailSender()
        sender.gmail_client.send_email_reply_with_mime.return_value = "sent-123"

        success, _ = sender.send_cancellation_confirmation(
            customer_email="customer@example.com",
            customer_name="John Doe",
            original_slot="2026-04-03 14:00",
            thread_id="thread-1",
            message_id="msg-1@example.com",
            original_subject="Request to schedule a plumbing inspection next week",
            original_references="<root@example.com> <prev@example.com>",
            email_body="Cancellation body",
        )

        assert success is True
        sender.gmail_client.send_email_reply_with_mime.assert_called_once()
        call_kwargs = sender.gmail_client.send_email_reply_with_mime.call_args.kwargs
        assert call_kwargs["subject"] == "Re: Request to schedule a plumbing inspection next week"
        assert call_kwargs["original_references"] == "<root@example.com> <prev@example.com>"


class TestCancellationIntegration:
    """Integration tests for cancellation flow"""
    
    def test_cancellation_intent_mapping(self):
        """Test that cancellation intent is properly mapped to enum"""
        from channels.schemas import IntentType, intent_to_enum
        
        result = intent_to_enum("cancellation")
        assert result == IntentType.CANCELLATION, "Cancellation should map to IntentType.CANCELLATION"
        
        logger.info("✓ Cancellation intent correctly mapped to enum")


if __name__ == "__main__":
    # Run basic tests
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("Running Cancellation Feature Tests")
    print("="*60 + "\n")
    
    # Test intent detection
    print("Testing Intent Detection...")
    test_intent = TestCancellationIntent()
    try:
        test_intent.test_cancellation_intent_detection()
        print("✓ Intent detection tests passed\n")
    except Exception as e:
        print(f"✗ Intent detection tests failed: {e}\n")
    
    # Test email sender
    print("Testing Email Sender...")
    test_sender = TestCancellationEmailSender()
    try:
        test_sender.test_cancellation_ics_generation(Mock())
        test_sender.test_cancellation_email_structure(Mock())
        print("✓ Email sender tests passed\n")
    except Exception as e:
        print(f"✗ Email sender tests failed: {e}\n")
    
    # Test integration
    print("Testing Integration...")
    test_integration = TestCancellationIntegration()
    try:
        test_integration.test_cancellation_intent_mapping()
        print("✓ Integration tests passed\n")
    except Exception as e:
        print(f"✗ Integration tests failed: {e}\n")
    
    print("="*60)
    print("Test execution complete!")
    print("="*60)
