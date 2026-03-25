"""
tests/test_instagram_watcher.py

Integration tests for InstagramWatcher.
Run with: pytest tests/test_instagram_watcher.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def watcher():
    with patch("channels.instagram.instagram_watcher.InstagramClient"), \
         patch("channels.instagram.instagram_watcher.EmailHistoryStore"):
        from channels.instagram.instagram_watcher import InstagramWatcher
        return InstagramWatcher(poll_interval=10)


def test_watcher_initialization(watcher):
    assert watcher.channel_name == "instagram"
    assert watcher.running is False
    assert watcher.poll_interval == 10


def test_watcher_deduplicates_messages(watcher):
    watcher._seen_message_ids.add("mid.already_seen")
    watcher.client.fetch_unread_messages.return_value = [
        {"message_id": "mid.already_seen", "sender_id": "111", "text": "Hi"}
    ]
    result = watcher.fetch_unread_messages()
    assert result == []


def test_watcher_returns_new_messages(watcher):
    watcher.client.fetch_unread_messages.return_value = [
        {"message_id": "mid.new_001", "sender_id": "222", "text": "Hello"}
    ]
    result = watcher.fetch_unread_messages()
    assert len(result) == 1
    assert result[0]["message_id"] == "mid.new_001"
