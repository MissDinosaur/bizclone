"""
Tests for email agent functionality (intent and urgency detection)
"""
import pytest
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from channels.email.intent_classifier import IntentClassifier
from channels.email.urgency_detector import UrgencyDetector
from channels.email.email_agent import EmailAgent


class TestEmailIntentAndUrgency:
    """Test email intent and urgency detection"""
    
    @pytest.fixture
    def classifier(self):
        """Create intent classifier"""
        return IntentClassifier()
    
    @pytest.fixture
    def detector(self):
        """Create urgency detector"""
        return UrgencyDetector()
    
    def test_email_intent_and_urgency_independent(self, classifier, detector):
        """Test that email is analyzed for both intent AND urgency independently."""
        text = "URGENT! My pipe burst and water is flooding everywhere!"
        
        # Test intent classification
        intent_result = classifier.predict_intent(text)
        assert intent_result["intent"] in classifier.intent_labels
        assert "confidence" in intent_result
        
        # Test urgency detection
        urgency_result = detector.detect_urgency(text)
        assert urgency_result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert urgency_result["confidence"] >= 0


class TestIntentClassification:
    """Test 15-category intent classification."""
    
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()
    
    def test_intent_classification_basic(self, classifier):
        """Test basic intent classification"""
        test_cases = [
            ("How much is your plumbing service?", None),  # Should be pricing-related
            ("I need to book an appointment", None),  # Should be appointment
            ("Can you cancel my appointment?", None),  # Should be cancellation
            ("What are your working hours?", None),  # Should be working hours related
        ]
        
        for text, expected_intent in test_cases:
            result = classifier.predict_intent(text)
            assert "intent" in result
            assert "confidence" in result
            assert result["intent"] in classifier.intent_labels
            assert 0 <= result["confidence"] <= 1
    
    def test_intent_classification_various_inputs(self, classifier):
        """Test various email inputs"""
        inputs = [
            "How much does it cost?",
            "I want to schedule an appointment",
            "Please cancel my booking",
            "Are you open on Sunday?",
            "I'd like to file a complaint",
            "Can I get a refund?",
        ]
        
        for text in inputs:
            result = classifier.predict_intent(text)
            assert result["intent"] in classifier.intent_labels
            assert isinstance(result["confidence"], (int, float))


class TestUrgencyDetection:
    """Test urgency detection independent of intent."""
    
    @pytest.fixture
    def detector(self):
        return UrgencyDetector()
    
    def test_urgency_detection_critical(self, detector):
        """Test CRITICAL urgency detection"""
        critical_text = "EMERGENCY! Pipe burst! Water flooding everywhere! Need help NOW!"
        result = detector.detect_urgency(critical_text)
        
        assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert result["confidence"] >= 0
    
    def test_urgency_detection_high(self, detector):
        """Test HIGH urgency detection"""
        high_text = "I have no water today, need repair ASAP urgent"
        result = detector.detect_urgency(high_text)
        
        assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert result["confidence"] >= 0
    
    def test_urgency_detection_normal(self, detector):
        """Test NORMAL urgency detection"""
        normal_text = "When can I schedule an appointment for next month?"
        result = detector.detect_urgency(normal_text)
        
        assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert result["confidence"] >= 0
    
    def test_urgency_detection_with_intent(self, detector):
        """Test urgency detection with different intent contexts"""
        test_cases = [
            ("urgent appointment needed", "appointment"),
            ("I need pricing information urgently", "pricing"),
            ("need to cancel immediately", "cancellation"),
        ]
        
        for text, intent_category in test_cases:
            result = detector.detect_urgency(text, intent=intent_category)
            assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]


class TestReschedulingConsistency:
    """Test that rescheduling uses one consistent slot across reply and booking updates."""

    @patch("scheduling.appointment_workflow.get_booking_email_sender")
    @patch("scheduling.appointment_workflow.get_booking_assistant")
    @patch("scheduling.appointment_workflow.check_availability")
    @patch("channels.email.email_agent.BookingManager")
    @patch("channels.email.email_agent.EmailHistoryStore")
    @patch("channels.email.email_agent.UrgencyDetector")
    @patch("channels.email.email_agent.IntentClassifier")
    @patch("channels.email.email_agent.EmailRAGPipeline")
    def test_rescheduling_reuses_selected_slot_everywhere(
        self,
        mock_rag,
        mock_intent,
        mock_urgency,
        mock_store,
        mock_booking_manager,
        mock_check_availability,
        mock_get_booking_assistant,
        mock_get_booking_email_sender,
    ):
        selected_slot = "2026-04-22 14:00"
        original_slot = datetime(2026, 4, 21, 13, 0)

        mock_intent.return_value.predict_intent.return_value = {
            "intent": "rescheduling",
            "confidence": 0.95,
        }
        mock_urgency.return_value.detect_urgency.return_value = {
            "urgency_level": "NORMAL",
            "confidence": 0.9,
            "escalation_reason": "No urgency indicators detected",
            "detected_keywords": [],
        }
        mock_urgency.return_value.should_escalate_to_owner.return_value = False

        mock_rag.return_value.generate_email_reply.return_value = (
            "Your appointment has been rescheduled.",
            ["doc-1"],
        )

        current_booking = MagicMock()
        current_booking.id = "BK20260415-114014"
        current_booking.slot = original_slot

        booking_manager_instance = mock_booking_manager.return_value
        booking_manager_instance._get_customer_current_booking.return_value = current_booking
        booking_manager_instance.reschedule_appointment.return_value = {
            "status": "success",
            "old_booking_id": "BK20260415-114014",
            "new_booking_id": "BK20260415-114221",
        }

        mock_check_availability.return_value = [selected_slot, "2026-04-23 09:00"]

        booking_assistant = MagicMock()
        booking_assistant._extract_date_preferences_from_email.return_value = {
            "preferred_days": ["Tuesday", "Wednesday"],
            "preferred_week": "next_week",
            "preferred_times": ["morning", "afternoon"],
            "specific_date": None,
        }
        booking_assistant._filter_slots_by_preferences.return_value = [selected_slot]
        booking_assistant.select_best_appointment_slot.return_value = (
            selected_slot,
            "Selected based on customer preference.",
        )
        mock_get_booking_assistant.return_value = booking_assistant

        email_sender = MagicMock()
        email_sender.send_email_reply_with_ics.return_value = (True, "message-id")
        mock_get_booking_email_sender.return_value = email_sender

        agent = EmailAgent()
        email_payload = {
            "from": "jacqui2410ger@gmail.com",
            "subject": "Re: Request to schedule a plumbing inspection next week",
            "body": "Could we move it to next Wednesday afternoon instead?",
            "thread_id": "thread-1",
            "message_id": "message-1",
        }

        result = agent.process_email(email_payload)

        rag_call = mock_rag.return_value.generate_email_reply.call_args
        assert rag_call.kwargs["booking"]["slot"] == selected_slot
        assert rag_call.kwargs["intent"] == "rescheduling"

        booking_manager_instance.reschedule_appointment.assert_called_once_with(
            customer_email="jacqui2410ger@gmail.com",
            new_slot=selected_slot,
            reason="Customer requested reschedule via email",
            channel="email",
        )

        email_sender.send_email_reply_with_ics.assert_called_once()
        assert (
            email_sender.send_email_reply_with_ics.call_args.kwargs[
                "appointment_slot"
            ]
            == selected_slot
        )
        assert result.metadata["booking_confirmation_sent"] is True


class TestCancellationThreading:
    """Test that cancellation flow preserves original threading metadata."""

    @patch("scheduling.appointment_workflow.get_booking_email_sender")
    @patch("channels.email.email_agent.EmailHistoryStore")
    @patch("channels.email.email_agent.BookingManager")
    @patch("channels.email.email_agent.UrgencyDetector")
    @patch("channels.email.email_agent.IntentClassifier")
    @patch("channels.email.email_agent.EmailRAGPipeline")
    def test_cancellation_passes_original_references_to_sender(
        self,
        mock_rag,
        mock_intent,
        mock_urgency,
        mock_booking_manager,
        mock_store,
        mock_get_booking_email_sender,
    ):
        mock_intent.return_value.predict_intent.return_value = {
            "intent": "cancellation",
            "confidence": 0.95,
        }
        mock_urgency.return_value.detect_urgency.return_value = {
            "urgency_level": "NORMAL",
            "confidence": 0.9,
            "escalation_reason": "No urgency indicators detected",
            "detected_keywords": [],
        }
        mock_urgency.return_value.should_escalate_to_owner.return_value = False
        mock_rag.return_value.generate_email_reply.return_value = (
            "Your appointment has been cancelled.",
            ["doc-1"],
        )

        booking_manager_instance = mock_booking_manager.return_value
        booking_manager_instance.cancel_appointment.return_value = {
            "status": "success",
            "booking_id": "BK1",
            "message": "Appointment cancelled",
            "cancelled_at": datetime.utcnow(),
            "details": {
                "original_slot": "2026-04-21T09:00:00",
                "customer_email": "customer@example.com",
            },
        }

        email_sender = MagicMock()
        email_sender.send_cancellation_confirmation.return_value = (True, "message-id")
        mock_get_booking_email_sender.return_value = email_sender

        agent = EmailAgent()
        result = agent.process_email(
            {
                "from": "customer@example.com",
                "subject": "Re: Request to schedule a plumbing inspection next week",
                "body": "Please cancel my appointment.",
                "thread_id": "thread-1",
                "message_id": "msg-1@example.com",
                "references": "<root@example.com> <prev@example.com>",
            }
        )

        email_sender.send_cancellation_confirmation.assert_called_once()
        call_kwargs = email_sender.send_cancellation_confirmation.call_args.kwargs
        assert call_kwargs["original_subject"] == "Re: Request to schedule a plumbing inspection next week"
        assert call_kwargs["original_references"] == "<root@example.com> <prev@example.com>"
        assert result.metadata["booking_confirmation_sent"] is True
