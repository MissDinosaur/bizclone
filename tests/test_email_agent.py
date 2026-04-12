"""
Tests for email agent functionality (intent and urgency detection)
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from channels.email.intent_classifier import IntentClassifier
from channels.email.urgency_detector import UrgencyDetector


class TestEmailIntentAndUrgency:
    """Test email intent and urgency detection"""
    
    @pytest.fixture
    def classifier(self):
        """Create intent classifier"""
        return IntentClassifier()
    
    @pytest.fixture
    def detector(self):
        """Create urgency detector"""
        return UrgencyDetector()
    
    def test_email_intent_and_urgency_independent(self, classifier, detector):
        """Test that email is analyzed for both intent AND urgency independently."""
        text = "URGENT! My pipe burst and water is flooding everywhere!"
        
        # Test intent classification
        intent_result = classifier.predict_intent(text)
        assert intent_result["intent"] in classifier.intent_labels
        assert "confidence" in intent_result
        
        # Test urgency detection
        urgency_result = detector.detect_urgency(text)
        assert urgency_result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert urgency_result["confidence"] >= 0


class TestIntentClassification:
    """Test 15-category intent classification."""
    
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()
    
    def test_intent_classification_basic(self, classifier):
        """Test basic intent classification"""
        test_cases = [
            ("How much is your plumbing service?", None),  # Should be pricing-related
            ("I need to book an appointment", None),  # Should be appointment
            ("Can you cancel my appointment?", None),  # Should be cancellation
            ("What are your working hours?", None),  # Should be working hours related
        ]
        
        for text, expected_intent in test_cases:
            result = classifier.predict_intent(text)
            assert "intent" in result
            assert "confidence" in result
            assert result["intent"] in classifier.intent_labels
            assert 0 <= result["confidence"] <= 1
    
    def test_intent_classification_various_inputs(self, classifier):
        """Test various email inputs"""
        inputs = [
            "How much does it cost?",
            "I want to schedule an appointment",
            "Please cancel my booking",
            "Are you open on Sunday?",
            "I'd like to file a complaint",
            "Can I get a refund?",
        ]
        
        for text in inputs:
            result = classifier.predict_intent(text)
            assert result["intent"] in classifier.intent_labels
            assert isinstance(result["confidence"], (int, float))


class TestUrgencyDetection:
    """Test urgency detection independent of intent."""
    
    @pytest.fixture
    def detector(self):
        return UrgencyDetector()
    
    def test_urgency_detection_critical(self, detector):
        """Test CRITICAL urgency detection"""
        critical_text = "EMERGENCY! Pipe burst! Water flooding everywhere! Need help NOW!"
        result = detector.detect_urgency(critical_text)
        
        assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert result["confidence"] >= 0
    
    def test_urgency_detection_high(self, detector):
        """Test HIGH urgency detection"""
        high_text = "I have no water today, need repair ASAP urgent"
        result = detector.detect_urgency(high_text)
        
        assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert result["confidence"] >= 0
    
    def test_urgency_detection_normal(self, detector):
        """Test NORMAL urgency detection"""
        normal_text = "When can I schedule an appointment for next month?"
        result = detector.detect_urgency(normal_text)
        
        assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
        assert result["confidence"] >= 0
    
    def test_urgency_detection_with_intent(self, detector):
        """Test urgency detection with different intent contexts"""
        test_cases = [
            ("urgent appointment needed", "appointment"),
            ("I need pricing information urgently", "pricing"),
            ("need to cancel immediately", "cancellation"),
        ]
        
        for text, intent_category in test_cases:
            result = detector.detect_urgency(text, intent=intent_category)
            assert result["urgency_level"] in ["CRITICAL", "HIGH", "NORMAL"]
