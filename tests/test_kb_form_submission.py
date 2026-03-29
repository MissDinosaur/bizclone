"""
Test script to verify KB form submission and data capture.
Tests:
1. Policy UPDATE with owner_correction value
2. FAQ INSERT with customer_question and owner_correction
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000/learning/feedback"

def test_policy_update():
    """Test updating a policy with owner_correction value"""
    logger.info("=" * 60)
    logger.info("TEST 1: Policy UPDATE with owner_correction")
    logger.info("=" * 60)
    
    payload = {
        "kb_field": "policy",
        "operation": "update",
        "customer_question": None,
        "owner_correction": "Emergency availability has been extended to include holiday support.",
        "policy_name": "emergency hours",
        "service_name": None,
        "service_description": None,
        "service_price": None
    }
    
    logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(API_URL, json=payload)
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def test_faq_insert():
    """Test inserting a new FAQ entry"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: FAQ INSERT with customer_question and owner_correction")
    logger.info("=" * 60)
    
    payload = {
        "kb_field": "faq",
        "operation": "insert",
        "customer_question": "Do you provide emergency service on weekends?",
        "owner_correction": "Yes, we provide 24/7 emergency plumbing services including weekends and holidays.",
        "policy_name": None,
        "service_name": None,
        "service_description": None,
        "service_price": None
    }
    
    logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(API_URL, json=payload)
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def test_policy_insert():
    """Test inserting a new policy"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Policy INSERT with policy_name and owner_correction")
    logger.info("=" * 60)
    
    payload = {
        "kb_field": "policy",
        "operation": "insert",
        "customer_question": None,
        "owner_correction": "We offer senior discounts of 15% on all services for customers over 65 years old.",
        "policy_name": "senior discount policy",
        "service_name": None,
        "service_description": None,
        "service_price": None
    }
    
    logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(API_URL, json=payload)
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


if __name__ == "__main__":
    results = []
    
    results.append(("Policy UPDATE", test_policy_update()))
    results.append(("FAQ INSERT", test_faq_insert()))
    results.append(("Policy INSERT", test_policy_insert()))
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
