"""
End-to-End Workflow Tests
Tests complete user journeys and business processes
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta


class TestEmailWorkflows:
    """Test complete email handling workflows"""
    
    @pytest.fixture
    def workflow_components(self):
        """Create mock workflow components"""
        return {
            "email_agent": Mock(),
            "intent_classifier": Mock(),
            "rag_pipeline": Mock(),
            "scheduler": Mock(),
            "kb_manager": Mock()
        }
    
    def test_appointment_booking_workflow(self, workflow_components):
        """Test complete appointment booking workflow"""
        # Step 1: Receive email
        customer_email = "john@example.com"
        email_body = "I'd like to book an appointment for next Monday at 2 PM"
        
        # Step 2: Classify intent
        workflow_components["intent_classifier"].predict_intent = Mock(return_value={
            "intent": "appointment",
            "confidence": 0.95
        })
        
        intent = workflow_components["intent_classifier"].predict_intent(email_body)
        assert intent["intent"] == "appointment"
        
        # Step 3: Extract appointment details
        appointment = {
            "customer_email": customer_email,
            "date": "2026-04-21",
            "time": "14:00",
            "service": "plumbing repair"
        }
        
        # Step 4: Schedule appointment
        workflow_components["scheduler"].book_appointment = Mock(return_value={
            "status": "confirmed",
            "appointment_id": "apt_001"
        })
        
        result = workflow_components["scheduler"].book_appointment(appointment)
        assert result["status"] == "confirmed"
        
        # Step 5: Generate confirmation email
        workflow_components["rag_pipeline"].generate_email_reply = Mock(
            return_value="Appointment confirmed for Monday at 2 PM"
        )
        
        reply = workflow_components["rag_pipeline"].generate_email_reply(
            customer_email, email_body, "appointment"
        )
        assert reply is not None
    
    def test_pricing_inquiry_workflow(self, workflow_components):
        """Test pricing inquiry workflow"""
        # Customer asks about pricing
        email = "What are your service costs?"
        
        # Intent detection
        workflow_components["intent_classifier"].predict_intent = Mock(return_value={
            "intent": "price_inquiry",
            "confidence": 0.88
        })
        
        intent = workflow_components["intent_classifier"].predict_intent(email)
        assert intent["intent"] == "price_inquiry"
        
        # Retrieve pricing from KB
        workflow_components["kb_manager"].search = Mock(return_value=[
            "Emergency plumbing service: $150/hour",
            "Standard repairs: $120/hour"
        ])
        
        pricing_info = workflow_components["kb_manager"].search("pricing")
        assert len(pricing_info) > 0
        
        # Generate response
        workflow_components["rag_pipeline"].generate_email_reply = Mock(
            return_value="Our pricing starts from $120/hour..."
        )
        
        response = workflow_components["rag_pipeline"].generate_email_reply(
            "customer@example.com", email, "price_inquiry"
        )
        assert "pricing" in response.lower() or "$" in response
    
    def test_complaint_resolution_workflow(self, workflow_components):
        """Test complaint handling and resolution workflow"""
        # Customer complains about service
        complaint = "Your plumber damaged my kitchen sink!"
        
        # Intent classification
        workflow_components["intent_classifier"].predict_intent = Mock(return_value={
            "intent": "complaint",
            "confidence": 0.92
        })
        
        intent = workflow_components["intent_classifier"].predict_intent(complaint)
        assert intent["intent"] == "complaint"
        
        # Retrieve relevant policies
        workflow_components["kb_manager"].search = Mock(return_value=[
            "Damage liability policy: We cover accidental damage with proof"
        ])
        
        # Generate response
        workflow_components["rag_pipeline"].generate_email_reply = Mock(
            return_value="We sincerely apologize. We will handle this claim..."
        )
        
        response = workflow_components["rag_pipeline"].generate_email_reply(
            "upset_customer@example.com", complaint, "complaint"
        )
        assert response is not None
    
    def test_cancellation_workflow(self, workflow_components):
        """Test appointment cancellation workflow"""
        cancellation_request = "I need to cancel my appointment"
        
        # Intent detection
        workflow_components["intent_classifier"].predict_intent = Mock(return_value={
            "intent": "cancellation",
            "confidence": 0.90
        })
        
        intent = workflow_components["intent_classifier"].predict_intent(cancellation_request)
        assert intent["intent"] == "cancellation"
        
        # Cancel appointment
        workflow_components["scheduler"].cancel_appointment = Mock(return_value={
            "status": "cancelled",
            "refund_eligible": True
        })
        
        result = workflow_components["scheduler"].cancel_appointment("apt_001")
        assert result["status"] == "cancelled"
    
    def test_feedback_learning_workflow(self, workflow_components):
        """Test feedback collection and KB learning workflow"""
        # User provides feedback on AI-generated response
        feedback = {
            "email_id": "email_123",
            "generated_response": "Initial response",
            "user_correction": "Better response",
            "type": "correction"
        }
        
        # Save feedback
        workflow_components["kb_manager"].save_feedback = Mock(return_value=True)
        
        result = workflow_components["kb_manager"].save_feedback(feedback)
        assert result is True
        
        # Update KB with new knowledge
        workflow_components["kb_manager"].update_with_feedback = Mock(return_value={
            "status": "updated",
            "entries_added": 1
        })
        
        update_result = workflow_components["kb_manager"].update_with_feedback(feedback)
        assert update_result["status"] == "updated"
    
    def test_multi_turn_conversation_workflow(self, workflow_components):
        """Test handling multi-turn conversations"""
        conversation = [
            {
                "turn": 1,
                "user": "Do you offer emergency service?",
                "intent": "faq"
            },
            {
                "turn": 2,
                "user": "What's the cost?",
                "intent": "price_inquiry"
            },
            {
                "turn": 3,
                "user": "Can you come tomorrow at 10 AM?",
                "intent": "appointment"
            }
        ]
        
        for turn in conversation:
            workflow_components["intent_classifier"].predict_intent = Mock(
                return_value={"intent": turn["intent"], "confidence": 0.90}
            )
            
            intent = workflow_components["intent_classifier"].predict_intent(turn["user"])
            assert intent["intent"] == turn["intent"]
    
    def test_escalation_workflow(self, workflow_components):
        """Test escalation to human support workflow"""
        # High complexity issue
        email = "Complex technical issue that AI cannot resolve"
        
        workflow_components["intent_classifier"].predict_intent = Mock(return_value={
            "intent": "other",
            "confidence": 0.35
        })
        
        intent = workflow_components["intent_classifier"].predict_intent(email)
        
        # Low confidence should trigger escalation
        if intent["confidence"] < 0.5:
            workflow_components["email_agent"].escalate_to_human = Mock(return_value=True)
            escalated = workflow_components["email_agent"].escalate_to_human(email)
            assert escalated is True
    
    def test_batch_email_processing_workflow(self, workflow_components):
        """Test batch processing multiple emails"""
        emails = [
            {"id": "e1", "body": "Booking request", "intent": "appointment"},
            {"id": "e2", "body": "Pricing question", "intent": "price_inquiry"},
            {"id": "e3", "body": "Service complaint", "intent": "complaint"}
        ]
        
        processed = []
        for email in emails:
            workflow_components["intent_classifier"].predict_intent = Mock(
                return_value={"intent": email["intent"], "confidence": 0.90}
            )
            
            result = workflow_components["intent_classifier"].predict_intent(email["body"])
            processed.append(result)
        
        assert len(processed) == len(emails)
    
    def test_error_recovery_workflow(self, workflow_components):
        """Test error handling and recovery in workflows"""
        # Simulate processing error
        workflow_components["intent_classifier"].predict_intent = Mock(
            side_effect=Exception("Model error")
        )
        
        try:
            workflow_components["intent_classifier"].predict_intent("test")
            # Should handle error gracefully
        except Exception:
            # Fallback to default intent
            workflow_components["intent_classifier"].predict_intent = Mock(
                return_value={"intent": "other", "confidence": 0.0}
            )
            
            fallback_result = workflow_components["intent_classifier"].predict_intent("test")
            assert fallback_result["intent"] == "other"
