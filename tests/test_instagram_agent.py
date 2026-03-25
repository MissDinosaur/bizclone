"""
tests/test_instagram_agent.py

Unit tests for the InstagramAgent.
Run with: pytest tests/test_instagram_agent.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from channels.instagram.instagram_agent import InstagramAgent
from channels.schemas import ChannelMessageResponseSchema, MessageStatus, IntentType


@pytest.fixture
def agent():
    with patch("channels.instagram.instagram_agent.IntentClassifier") as MockIC, \
         patch("channels.instagram.instagram_agent.EmailRAGPipeline") as MockRAG:

        mock_ic = MockIC.return_value
        mock_ic.classify.return_value = "faq"

        mock_rag = MockRAG.return_value
        mock_rag.query.return_value = {
            "answer": "We have a great selection of rugs!",
            "source_documents": [],
        }

        yield InstagramAgent()


@pytest.fixture
def sample_message():
    return {
        "from": "123456789",
        "name": "Test User",
        "body": "Do you have silk rugs?",
        "message_id": "mid.abc123",
        "timestamp": "2026-03-25T10:00:00+0000",
        "channel": "instagram",
    }


def test_agent_returns_correct_schema(agent, sample_message):
    result = agent.process_message(sample_message)
    assert isinstance(result, ChannelMessageResponseSchema)


def test_agent_channel_is_instagram(agent, sample_message):
    result = agent.process_message(sample_message)
    assert result.channel == "instagram"


def test_agent_auto_send_on_faq(agent, sample_message):
    result = agent.process_message(sample_message)
    assert result.status == MessageStatus.AUTO_SEND


def test_agent_reply_is_not_empty(agent, sample_message):
    result = agent.process_message(sample_message)
    assert result.reply and len(result.reply) > 0


def test_agent_handles_empty_text(agent):
    message = {
        "from": "999",
        "name": "",
        "body": "",
        "message_id": "mid.empty",
        "timestamp": "",
        "channel": "instagram",
    }
    result = agent.process_message(message)
    assert isinstance(result, ChannelMessageResponseSchema)


def test_agent_returns_failed_on_pipeline_error(sample_message):
    with patch("channels.instagram.instagram_agent.IntentClassifier") as MockIC, \
         patch("channels.instagram.instagram_agent.EmailRAGPipeline"):

        MockIC.return_value.classify.side_effect = RuntimeError("Model error")
        agent = InstagramAgent()

    result = agent.process_message(sample_message)
    assert result.status == MessageStatus.FAILED
    assert result.error_code == "AGENT_ERROR"
