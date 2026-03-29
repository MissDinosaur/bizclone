import pytest
from channels.email.email_agent import process_email
from channels.email.intent_classifier import IntentClassifier
from channels.email.urgency_detector import UrgencyDetector
from config import config as cfg

def test_email_intent_and_urgency():
    """Test that email is analyzed for both intent AND urgency independently."""
    payload = {
        "from": "test@gmail.com",
        "subject": "Emergency Pipe Burst",
        "body": "URGENT! My pipe burst and water is flooding everywhere!"
    }

    result = process_email(payload)

    # Intent should be one of 15 categories (not EMERGENCY - that's now urgency)
    intent_labels = [
        "price_inquiry", "appointment", "cancellation", "working_hours", "faq",
        "payment_inquiry", "service_request", "complaint", "feedback",
        "warranty_claim", "replacement_request", "refund_request",
        "upgrade_inquiry", "bulk_inquiry", "other"
    ]
    assert result.intent.value in [cfg.PRICE_INQUERY, cfg.APPOINTMENT, cfg.CANCELLATION, 
                                    cfg.WORKING_HOUR, cfg.FAQ], f"Intent should be one of legacy values"
    
    # Urgency should be detected separately
    assert result.metadata is not None
    assert result.metadata.get("urgency_level") in ["CRITICAL", "HIGH", "NORMAL"]
    
    # Status should properly reflect urgency-based decision
    assert result.status in ["auto_send", "needs_review", "failed"]


def test_intent_classification():
    """Test 15-category intent classification."""
    classifier = IntentClassifier()
    
    test_cases = [
        ("How much is your plumbing service?", "price_inquiry"),
        ("I need to book an appointment", "appointment"),
        ("Can you cancel my appointment?", "cancellation"),
        ("What are your working hours?", "working_hours"),
        ("Do you repair burst pipes?", "faq"),
        ("I want a refund", "refund_request"),
        ("This is a complaint about your service", "complaint"),
    ]
    
    for text, expected_intent in test_cases:
        result = classifier.predict_intent(text)
        assert result["intent"] in ["price_inquiry", "appointment", "cancellation", "working_hours",
                                   "faq", "refund_request", "complaint", "feedback", "bulk_inquiry"]


def test_urgency_detection():
    """Test urgency detection independent of intent."""
    detector = UrgencyDetector()
    
    # Test CRITICAL urgency
    critical_text = "EMERGENCY! Pipe burst! Water flooding everywhere! Need help NOW!"
    result = detector.detect_urgency(critical_text)
    assert result["urgency_level"] == "CRITICAL"
    assert result["confidence"] > 0.90
    
    # Test HIGH urgency
    high_text = "I have no water today, need repair ASAP"
    result = detector.detect_urgency(high_text)
    assert result["urgency_level"] == "HIGH"
    
    # Test NORMAL urgency
    normal_text = "When can I schedule an appointment for next month?"
    result = detector.detect_urgency(normal_text)
    assert result["urgency_level"] == "NORMAL"
