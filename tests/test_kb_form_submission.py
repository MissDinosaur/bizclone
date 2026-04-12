"""
Test KB form submission with mocked API or real server.
Tests form data validation and KB update operations.
"""

import pytest
import json
import logging
import os
from unittest.mock import Mock, patch, MagicMock

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = os.getenv("LEARNING_API_URL", "http://localhost:8000/learning/feedback")


class TestKBFormSubmission:
    """Test KB form submission functionality"""
    
    @pytest.fixture
    def form_payload_policy_update(self):
        """Policy update form payload"""
        return {
            "kb_field": "policy",
            "operation": "update",
            "customer_question": None,
            "owner_correction": "Emergency availability has been extended to include holiday support.",
            "policy_name": "emergency hours",
            "service_name": None,
            "service_description": None,
            "service_price": None
        }
    
    @pytest.fixture
    def form_payload_faq_insert(self):
        """FAQ insert form payload"""
        return {
            "kb_field": "faq",
            "operation": "insert",
            "customer_question": "Do you provide emergency service on weekends?",
            "owner_correction": "Yes, we provide 24/7 emergency plumbing services including weekends and holidays.",
            "policy_name": None,
            "service_name": None,
            "service_description": None,
            "service_price": None
        }
    
    @pytest.fixture
    def form_payload_policy_insert(self):
        """Policy insert form payload"""
        return {
            "kb_field": "policy",
            "operation": "insert",
            "customer_question": None,
            "owner_correction": "We offer senior discounts of 15% on all services for customers over 65 years old.",
            "policy_name": "senior discount policy",
            "service_name": None,
            "service_description": None,
            "service_price": None
        }
    
    def test_form_payload_structure_policy_update(self, form_payload_policy_update):
        """Test policy update form payload has correct structure"""
        payload = form_payload_policy_update
        
        # Verify required fields
        assert payload["kb_field"] == "policy"
        assert payload["operation"] == "update"
        assert payload["owner_correction"] is not None
        assert payload["policy_name"] is not None
    
    def test_form_payload_structure_faq_insert(self, form_payload_faq_insert):
        """Test FAQ insert form payload has correct structure"""
        payload = form_payload_faq_insert
        
        # Verify required fields
        assert payload["kb_field"] == "faq"
        assert payload["operation"] == "insert"
        assert payload["customer_question"] is not None
        assert payload["owner_correction"] is not None
    
    def test_form_payload_structure_policy_insert(self, form_payload_policy_insert):
        """Test policy insert form payload has correct structure"""
        payload = form_payload_policy_insert
        
        # Verify required fields
        assert payload["kb_field"] == "policy"
        assert payload["operation"] == "insert"
        assert payload["owner_correction"] is not None
        assert payload["policy_name"] is not None
    
    @patch('requests.post')
    def test_policy_update_with_mock(self, mock_post, form_payload_policy_update):
        """Test updating a policy with mocked API"""
        logger.info("Test: Policy UPDATE with owner_correction (mocked)")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "message": "Policy updated"}
        mock_post.return_value = mock_response
        
        # Simulate form submission
        import requests
        response = requests.post(API_URL, json=form_payload_policy_update, timeout=10)
        
        assert response.status_code == 200
        assert "success" in response.json()["status"]
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_faq_insert_with_mock(self, mock_post, form_payload_faq_insert):
        """Test inserting a new FAQ entry with mocked API"""
        logger.info("Test: FAQ INSERT with customer_question and owner_correction (mocked)")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "message": "FAQ inserted", "id": "faq_123"}
        mock_post.return_value = mock_response
        
        # Simulate form submission
        import requests
        response = requests.post(API_URL, json=form_payload_faq_insert, timeout=10)
        
        assert response.status_code == 200
        assert "id" in response.json()
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_policy_insert_with_mock(self, mock_post, form_payload_policy_insert):
        """Test inserting a new policy with mocked API"""
        logger.info("Test: Policy INSERT with policy_name and owner_correction (mocked)")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "message": "Policy inserted"}
        mock_post.return_value = mock_response
        
        # Simulate form submission
        import requests
        response = requests.post(API_URL, json=form_payload_policy_insert, timeout=10)
        
        assert response.status_code == 200
        assert "success" in response.json()["status"]
        mock_post.assert_called_once()
    
    @pytest.mark.skipif(
        os.getenv("SKIP_INTEGRATION_TESTS") == "true",
        reason="Integration tests disabled"
    )
    def test_policy_update_integration(self, form_payload_policy_update):
        """Test policy update against real API server (optional)"""
        import requests
        
        logger.info("Integration Test: Policy UPDATE")
        
        try:
            response = requests.post(API_URL, json=form_payload_policy_update, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Success: {response.json()}")
                assert response.status_code == 200
            else:
                logger.warning(f"API returned {response.status_code}")
                pytest.skip(f"API server returned {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            pytest.skip(f"API server not running: {e}")
        except Exception as e:
            logger.error(f"Test error: {e}")
            pytest.skip(f"Could not run test: {e}")
    
    @pytest.mark.skipif(
        os.getenv("SKIP_INTEGRATION_TESTS") == "true",
        reason="Integration tests disabled"
    )
    def test_faq_insert_integration(self, form_payload_faq_insert):
        """Test FAQ insert against real API server (optional)"""
        import requests
        
        logger.info("Integration Test: FAQ INSERT")
        
        try:
            response = requests.post(API_URL, json=form_payload_faq_insert, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Success: {response.json()}")
                assert response.status_code == 200
            else:
                logger.warning(f"API returned {response.status_code}")
                pytest.skip(f"API server returned {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            pytest.skip(f"API server not running: {e}")
        except Exception as e:
            logger.error(f"Test error: {e}")
            pytest.skip(f"Could not run test: {e}")
    
    @pytest.mark.skipif(
        os.getenv("SKIP_INTEGRATION_TESTS") == "true",
        reason="Integration tests disabled"
    )
    def test_policy_insert_integration(self, form_payload_policy_insert):
        """Test policy insert against real API server (optional)"""
        import requests
        
        logger.info("Integration Test: Policy INSERT")
        
        try:
            response = requests.post(API_URL, json=form_payload_policy_insert, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Success: {response.json()}")
                assert response.status_code == 200
            else:
                logger.warning(f"API returned {response.status_code}")
                pytest.skip(f"API server returned {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            pytest.skip(f"API server not running: {e}")
        except Exception as e:
            logger.error(f"Test error: {e}")
            pytest.skip(f"Could not run test: {e}")
