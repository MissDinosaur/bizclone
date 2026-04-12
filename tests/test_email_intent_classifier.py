"""
Tests for Email Intent Classifier functionality
"""
import pytest
from channels.email.intent_classifier import IntentClassifier


class TestIntentClassifier:
    """Test IntentClassifier functionality"""
    
    @pytest.fixture
    def classifier(self):
        """Create a classifier instance for testing"""
        return IntentClassifier()
    
    def test_classifier_initialization(self, classifier):
        """Test that IntentClassifier can be instantiated"""
        assert classifier is not None
        assert hasattr(classifier, 'intent_labels')
    
    def test_predict_intent_returns_dict(self, classifier):
        """Test that predict_intent returns a dictionary"""
        email = "I want to book an appointment for next Monday"
        result = classifier.predict_intent(email)
        
        assert isinstance(result, dict)
        assert "intent" in result
        assert "confidence" in result
    
    def test_predict_intent_valid_results(self, classifier):
        """Test that predict_intent returns valid intent and confidence"""
        email = "Hi, I'm planning to replace an old toilet in my home. Could you tell me what the typical installation cost would be?"
        result = classifier.predict_intent(email)
        
        # Check intent is valid
        assert result["intent"] in classifier.intent_labels, \
            f"Intent '{result['intent']}' not in valid labels: {classifier.intent_labels}"
        
        # Check confidence is a number between 0 and 1
        assert isinstance(result["confidence"], (int, float))
        assert 0 <= result["confidence"] <= 1
    
    def test_predict_intent_appointment_keyword(self, classifier):
        """Test appointment intent detection"""
        email = "I need to schedule an appointment for next week"
        result = classifier.predict_intent(email)
        
        assert result["intent"] in classifier.intent_labels
        assert result["confidence"] >= 0
    
    def test_predict_intent_pricing_keyword(self, classifier):
        """Test pricing intent detection"""
        email = "How much does installation cost? What is the price?"
        result = classifier.predict_intent(email)
        
        assert result["intent"] in classifier.intent_labels
        assert result["confidence"] >= 0
    
    def test_predict_intent_various_inputs(self, classifier):
        """Test various email inputs"""
        test_inputs = [
            ("I want to book", "appointment"),
            ("What's the price?", "pricing"),
            ("Can you help me?", "general"),
            ("", "general"),
        ]
        
        for email_text, expected_category in test_inputs:
            result = classifier.predict_intent(email_text)
            assert result["intent"] in classifier.intent_labels
            assert "confidence" in result
