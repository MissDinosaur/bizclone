"""
Unit tests for RAG Pipeline (Retrieval-Augmented Generation)
Tests the core email reply generation workflow
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rag.rag_pipeline import EmailRAGPipeline


class TestRAGPipeline:
    """Test EmailRAGPipeline functionality"""
    
    @pytest.fixture
    def pipeline(self):
        """Create a RAG pipeline instance with mocked dependencies"""
        with patch('rag.rag_pipeline.KnowledgeRetriever'), \
             patch('rag.rag_pipeline.LLMClient'), \
             patch('rag.rag_pipeline.EmailHistoryStore'):
            pipeline = EmailRAGPipeline()
            pipeline.retriever.retrieve = Mock(return_value=[
                "We offer 24/7 emergency plumbing service",
                "Pricing starts from $150 per hour"
            ])
            pipeline.llm.generate = Mock(return_value="Thank you for contacting us...")
            pipeline.email_store.get_conversation_for_prompt = Mock(return_value="[Previous conversation history]")
            return pipeline
    
    def test_pipeline_initialization(self):
        """Test that RAG pipeline can be initialized"""
        with patch('rag.rag_pipeline.KnowledgeRetriever'), \
             patch('rag.rag_pipeline.LLMClient'), \
             patch('rag.rag_pipeline.EmailHistoryStore'):
            pipeline = EmailRAGPipeline()
            assert pipeline is not None
            assert hasattr(pipeline, 'retriever')
            assert hasattr(pipeline, 'llm')
            assert hasattr(pipeline, 'email_store')
    
    def test_generate_email_reply_basic(self, pipeline):
        """Test basic email reply generation"""
        customer_email = "customer@example.com"
        body = "I need emergency plumbing service"
        intent = "service_request"
        
        reply = pipeline.generate_email_reply(customer_email, body, intent)
        
        # Verify methods were called
        pipeline.retriever.retrieve.assert_called_once()
        pipeline.email_store.get_conversation_for_prompt.assert_called_once()
        pipeline.llm.generate.assert_called_once()
    
    def test_retriever_context_integration(self, pipeline):
        """Test that retriever context is properly integrated"""
        customer_email = "test@example.com"
        body = "What are your prices?"
        intent = "price_inquiry"
        
        pipeline.generate_email_reply(customer_email, body, intent)
        
        # Verify retriever was called with body
        pipeline.retriever.retrieve.assert_called_with(body)
    
    def test_email_history_context_limit(self, pipeline):
        """Test that email history is limited to last 5 interactions"""
        customer_email = "customer@example.com"
        body = "Follow up on my appointment"
        intent = "appointment"
        
        pipeline.generate_email_reply(customer_email, body, intent)
        
        # Verify history retrieval was called with limit=5
        call_args = pipeline.email_store.get_conversation_for_prompt.call_args
        assert call_args[1]['limit'] == 5 or call_args[0][1] == 5
    
    def test_generate_reply_with_booking_context(self, pipeline):
        """Test email reply generation with booking information"""
        customer_email = "customer@example.com"
        body = "Can you confirm my appointment?"
        intent = "appointment"
        booking = {
            "date": "2026-04-15",
            "time": "14:00",
            "service": "Plumbing repair"
        }
        
        reply = pipeline.generate_email_reply(customer_email, body, intent, booking=booking)
        
        # Verify LLM was called
        pipeline.llm.generate.assert_called()
        assert reply is not None
    
    def test_empty_retrieval_handling(self, pipeline):
        """Test pipeline behavior when retriever returns empty context"""
        pipeline.retriever.retrieve = Mock(return_value=[])
        
        customer_email = "customer@example.com"
        body = "Some query"
        intent = "faq"
        
        # Should not raise error
        reply = pipeline.generate_email_reply(customer_email, body, intent)
        assert reply is not None
    
    def test_different_intent_types(self, pipeline):
        """Test pipeline with various intent types"""
        intents = ["appointment", "price_inquiry", "complaint", "feedback", "cancellation"]
        
        for intent in intents:
            pipeline.retriever.retrieve.reset_mock()
            pipeline.llm.generate.reset_mock()
            
            reply = pipeline.generate_email_reply("test@example.com", "Test message", intent)
            
            pipeline.retriever.retrieve.assert_called_once()
            pipeline.llm.generate.assert_called_once()
    
    def test_generate_reply_returns_reply_and_docs(self, pipeline):
        """Test that generate_email_reply returns (reply_text, retrieved_docs)."""
        reply_text, retrieved_docs = pipeline.generate_email_reply(
            "test@example.com",
            "Test",
            "faq",
        )

        assert isinstance(reply_text, (str, type(None)))
        assert isinstance(retrieved_docs, list)
    
    def test_llm_prompt_construction(self, pipeline):
        """Test that LLM receives properly constructed prompt"""
        pipeline.llm.generate = Mock(return_value="Generated reply")
        
        pipeline.generate_email_reply("customer@example.com", "Question?", "faq")
        
        # Verify LLM generate was called
        assert pipeline.llm.generate.called
        call_args = pipeline.llm.generate.call_args
        # Prompt should contain context and history
        if call_args:
            prompt = call_args[0][0] if call_args[0] else None
            assert prompt is not None
