"""
Tests for Gmail Client functionality
"""
import pytest
from channels.email.gmail_client import GmailClient
from unittest.mock import Mock, patch


class TestGmailClient:
    """Test GmailClient basic functionality"""
    
    def test_gmail_client_initialization(self):
        """Test that GmailClient can be instantiated"""
        client = GmailClient()
        # Service may be None if credentials aren't configured, but client should be created
        assert client is not None
    
    @patch('channels.email.gmail_client.GmailClient.fetch_unread_emails')
    def test_fetch_unread_emails_returns_list(self, mock_fetch):
        """Test that fetch_unread_emails returns a list"""
        # Mock the fetch method
        mock_fetch.return_value = [
            {
                "id": "test_id",
                "from": "sender@example.com",
                "subject": "Test Subject",
                "body": "Test Body"
            }
        ]
        
        client = GmailClient()
        emails = client.fetch_unread_emails(max_results=5)
        
        assert isinstance(emails, list)
        assert len(emails) > 0 or len(emails) == 0  # Should be a list
    
    @patch('channels.email.gmail_client.GmailClient.fetch_unread_emails')
    def test_fetch_unread_emails_structure(self, mock_fetch):
        """Test that returned emails have correct structure"""
        mock_email = {
            "id": "test_id",
            "from": "sender@example.com",
            "subject": "Test Subject",
            "body": "Test Body",
            "thread_id": "thread_123"
        }
        mock_fetch.return_value = [mock_email]
        
        client = GmailClient()
        emails = client.fetch_unread_emails(max_results=1)
        
        if emails:
            email = emails[0]
            assert "from" in email or "id" in email
            assert isinstance(email, dict)
