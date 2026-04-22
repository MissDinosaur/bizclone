"""
Unit tests for LLM Client
Tests language model interactions and response generation
"""

import pytest
from unittest.mock import Mock, patch


class TestLLMClient:
    """Test LLM Client functionality"""
    
    @pytest.fixture
    def llm_client(self):
        """Create LLM client with mocked OpenAI dependency."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
             patch("llm_engine.llm_client.OpenAI"):
            from llm_engine.llm_client import LLMClient
            return LLMClient()
    
    def test_llm_client_initialization(self):
        """Test LLM client can be initialized"""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
             patch("llm_engine.llm_client.OpenAI"):
            from llm_engine.llm_client import LLMClient
            client = LLMClient()
            assert client is not None
            assert client.client is not None

    def test_init_requires_api_key(self):
        """Initialization should fail when OPENAI_API_KEY is missing."""
        with patch.dict("os.environ", {}, clear=True):
            from llm_engine.llm_client import LLMClient
            with pytest.raises(ValueError):
                LLMClient()
    
    def test_generate_response_basic(self, llm_client):
        """Test basic response generation"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Generated response"
        mock_response.choices = [mock_choice]
        llm_client.client.chat.completions.create = Mock(return_value=mock_response)
        
        prompt = "Generate a professional email response."
        response = llm_client.generate(prompt)
        assert response == "Generated response"
    
    def test_generate_with_temperature(self, llm_client):
        """Test response generation with temperature control"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_response.choices = [mock_choice]
        llm_client.client.chat.completions.create = Mock(return_value=mock_response)

        llm_client.generate("Prompt")
        call_kwargs = llm_client.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3
    
    def test_context_preservation(self, llm_client):
        """Test that context is preserved in responses"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Contextual response"
        mock_response.choices = [mock_choice]
        llm_client.client.chat.completions.create = Mock(return_value=mock_response)
        
        context = "Customer wants to book an appointment"
        prompt = f"Context: {context}\nGenerate response."
        
        llm_client.generate(prompt)
        messages = llm_client.client.chat.completions.create.call_args.kwargs["messages"]
        assert any(context in m["content"] for m in messages)
    
    def test_error_handling_invalid_prompt(self, llm_client):
        """Test error handling for invalid prompts"""
        llm_client.client.chat.completions.create = Mock(side_effect=ValueError("Invalid input"))
        response = llm_client.generate("bad prompt")
        assert response == "Thank you for your email. We will respond shortly."
    
    def test_batch_generation(self, llm_client):
        """Test batch generating multiple responses"""
        prompts = [
            "Generate response 1",
            "Generate response 2",
            "Generate response 3"
        ]
        
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_response.choices = [mock_choice]
        llm_client.client.chat.completions.create = Mock(return_value=mock_response)

        responses = [llm_client.generate(prompt) for prompt in prompts]
        assert len(responses) == 3
    
    def test_response_format_text(self, llm_client):
        """Test response is returned as text"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Sample text response"
        mock_response.choices = [mock_choice]
        llm_client.client.chat.completions.create = Mock(return_value=mock_response)

        response = llm_client.generate("Prompt")
        assert isinstance(response, str)
    
    def test_prompt_engineering_structure(self, llm_client):
        """Test structured prompt engineering"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_response.choices = [mock_choice]
        llm_client.client.chat.completions.create = Mock(return_value=mock_response)
        
        structured_prompt = """
        Customer Intent: appointment booking
        Customer Email: Request for appointment
        Business Context: 24/7 plumbing service
        
        Generate appropriate response:
        """
        
        llm_client.generate(structured_prompt)
        call_kwargs = llm_client.client.chat.completions.create.call_args.kwargs
        assert "messages" in call_kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
