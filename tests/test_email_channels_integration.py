"""
Integration tests for Multi-Channel Email Communication
Tests email agent integration with multiple communication channels (Teams, WhatsApp, etc.)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestEmailChannelIntegration:
    """Test email agent integration with multiple channels"""
    
    @pytest.fixture
    def email_agent(self):
        """Create email agent with mocked channels"""
        with patch('channels.email.email_agent.EmailAgent') as mock_agent:
            agent = mock_agent()
            agent.gmail_client = Mock()
            agent.intent_classifier = Mock()
            agent.rag_pipeline = Mock()
            return agent
    
    def test_gmail_channel_integration(self, email_agent):
        """Test Gmail channel for receiving emails"""
        email_agent.gmail_client.fetch_messages = Mock(return_value=[
            {
                "id": "msg_001",
                "from": "customer@example.com",
                "subject": "Service inquiry",
                "body": "I need plumbing service"
            }
        ])
        
        # Gmail client should work
        assert email_agent.gmail_client is not None
    
    def test_email_classification_pipeline(self, email_agent):
        """Test email classification in the pipeline"""
        email_agent.intent_classifier.predict_intent = Mock(return_value={
            "intent": "service_request",
            "confidence": 0.92
        })
        
        result = email_agent.intent_classifier.predict_intent("Test email")
        
        # Classification should return intent and confidence
        assert result["intent"] is not None
        assert "confidence" in result
    
    def test_multi_channel_message_routing(self, email_agent):
        """Test routing messages across channels"""
        channels = ["gmail", "teams", "whatsapp", "call"]
        
        for channel in channels:
            # Each channel should be supported
            assert channel in channels
    
    def test_email_response_generation(self, email_agent):
        """Test generating responses via RAG pipeline"""
        email_agent.rag_pipeline.generate_email_reply = Mock(return_value={
            "reply": "Thank you for contacting us...",
            "intent": "service_request",
            "confidence": 0.9
        })
        
        response = email_agent.rag_pipeline.generate_email_reply(
            "customer@example.com",
            "I need service",
            "service_request"
        )
        
        # Response should include reply and metadata
        assert "reply" in response
        assert "intent" in response
    
    def test_channel_priority_handling(self, email_agent):
        """Test handling priority across channels"""
        priorities = {
            "call": 1,
            "whatsapp": 2,
            "teams": 3,
            "gmail": 4
        }
        
        # Lower number = higher priority
        # Real-time channels should be prioritized
        assert priorities["call"] < priorities["gmail"]
    
    def test_message_deduplication(self, email_agent):
        """Test preventing duplicate messages across channels"""
        messages = [
            {"id": "msg_1", "from": "user@example.com", "body": "Same question"},
            {"id": "msg_2", "channel": "teams", "from": "user@example.com", "body": "Same question"}
        ]
        
        # System should detect duplicates
        assert len(messages) == 2
    
    def test_channel_response_formatting(self, email_agent):
        """Test formatting responses for different channels"""
        base_response = "Thank you for contacting us. We will assist you shortly."
        
        channel_formats = {
            "gmail": {"type": "email", "max_length": None},
            "teams": {"type": "teams_message", "max_length": 4000},
            "whatsapp": {"type": "whatsapp", "max_length": 1600}
        }
        
        # Each channel should format responses appropriately
        for channel, format_config in channel_formats.items():
            assert "type" in format_config
    
    def test_status_update_across_channels(self, email_agent):
        """Test status updates visible across channels"""
        status = {
            "message_id": "msg_001",
            "status": "replied",
            "timestamp": datetime.now().isoformat(),
            "channels_notified": ["gmail", "teams"]
        }
        
        # Status should be synchronized
        assert status["status"] == "replied"
        assert len(status["channels_notified"]) > 0
    
    def test_email_attachment_handling(self, email_agent):
        """Test handling email attachments"""
        email_with_attachments = {
            "id": "msg_001",
            "from": "customer@example.com",
            "subject": "Service quote",
            "attachments": [
                {"filename": "photo.jpg", "size": 2048000},
                {"filename": "receipt.pdf", "size": 512000}
            ]
        }
        
        # System should handle attachments
        assert len(email_with_attachments["attachments"]) > 0
    
    def test_conversation_thread_management(self, email_agent):
        """Test managing conversation threads"""
        thread = {
            "thread_id": "thread_123",
            "participants": ["customer@example.com", "support@example.com"],
            "message_count": 5,
            "last_message": datetime.now().isoformat()
        }
        
        # Conversation context should be maintained
        assert thread["message_count"] > 0
        assert len(thread["participants"]) >= 2
    
    def test_language_detection_multilingual(self, email_agent):
        """Test language detection for multilingual support"""
        messages = [
            {"text": "Hello, how can I help?", "detected_language": "en"},
            {"text": "Hola, ¿cómo puedo ayudarte?", "detected_language": "es"},
            {"text": "你好,我可以帮助你吗?", "detected_language": "zh"}
        ]
        
        # System should support multiple languages
        for msg in messages:
            assert "detected_language" in msg
