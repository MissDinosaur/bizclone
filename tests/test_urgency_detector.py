"""
Tests for improved Urgency Detector
Validates that urgency detection accuracy has improved
"""

import pytest
from channels.email.urgency_detector import UrgencyDetector


class TestUrgencyDetector:
    """Test urgency detection with various email scenarios"""

    @pytest.fixture
    def detector(self):
        """Create urgency detector instance"""
        return UrgencyDetector()

    # ============ CRITICAL URGENCY TESTS ============

    def test_detect_flooding_emergency(self, detector):
        """Test detection of flooding emergency"""
        email = "Subject: HELP - Pipe burst! Water flooding everywhere!"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "CRITICAL"
        assert result["confidence"] >= 0.90
        assert len(result["detected_keywords"]) > 0

    def test_detect_gas_leak(self, detector):
        """Test detection of gas leak - CRITICAL"""
        email = "Gas leak detected! Smell of gas in kitchen. Emergency!"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "CRITICAL"
        assert result["confidence"] >= 0.90

    def test_detect_immediate_emergency(self, detector):
        """Test detection of immediate emergency"""
        email = "EMERGENCY - Water damage immediate action needed NOW!"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "CRITICAL"
        assert result["confidence"] >= 0.90

    # ============ HIGH URGENCY TESTS ============

    def test_detect_time_bound_request(self, detector):
        """Test detection of time-bound request"""
        email = "Subject: Service needed within 24 hours\nBody: Please come today if possible"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "HIGH"
        assert result["confidence"] >= 0.75

    def test_detect_no_water_issue(self, detector):
        """Test detection of no water service issue"""
        email = "We have no hot water in the apartment and it's broken"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "HIGH"
        assert result["confidence"] >= 0.70

    def test_detect_complaint_with_urgency(self, detector):
        """Test detection of complaint with urgency"""
        email = "I'm very unhappy with the service. This is unacceptable and needs fixing today"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "HIGH"
        assert result["confidence"] >= 0.75

    def test_detect_repeat_issue(self, detector):
        """Test detection of recurring/repeat problem"""
        email = "This happened again! Already reported this twice, still broken"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "HIGH"
        assert result["confidence"] >= 0.70

    def test_detect_with_emergency_intent(self, detector):
        """Test HIGH detection with emergency service intent"""
        email = "When can you come? Need service soon"
        result = detector.detect_urgency(email, intent="emergency_service")
        
        assert result["urgency_level"] == "HIGH"
        assert "intent" in result["escalation_reason"].lower()

    # ============ NORMAL URGENCY TESTS ============

    def test_detect_normal_inquiry(self, detector):
        """Test detection of normal service inquiry"""
        email = "Hello, I'd like to know about your pricing for plumbing services"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "NORMAL"
        assert result["confidence"] >= 0.85

    def test_detect_scheduling_request(self, detector):
        """Test detection of normal scheduling request"""
        email = "What times are available for an appointment next week?"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "NORMAL"

    # ============ NEGATION TESTS (Reduced Urgency) ============

    def test_negation_not_urgent(self, detector):
        """Test that 'not urgent' reduces urgency"""
        email = "Need service but it's not urgent, can wait"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "NORMAL"
        assert "negation" in result["escalation_reason"].lower()

    def test_negation_can_wait(self, detector):
        """Test that 'can wait' indicates low urgency"""
        email = "Something is broken but can wait, not emergency"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "NORMAL"

    def test_negation_not_emergency(self, detector):
        """Test that 'not emergency' indicates low urgency"""
        email = "There's a problem but it's not an emergency"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "NORMAL"

    # ============ FORMAT/INTENSITY TESTS ============

    def test_format_multiple_exclamation_marks(self, detector):
        """Test that multiple exclamation marks boost confidence"""
        email_normal = "We have no water"
        email_intense = "We have no water!!!"
        
        result_normal = detector.detect_urgency(email_normal)
        result_intense = detector.detect_urgency(email_intense)
        
        # Both should be HIGH, but intense should have higher confidence
        assert result_normal["urgency_level"] in ["HIGH", "NORMAL"]
        assert result_intense["urgency_level"] == "HIGH"
        if result_intense["urgency_level"] == "HIGH":
            assert result_intense["confidence"] >= result_normal.get("confidence", 0)

    def test_format_all_caps(self, detector):
        """Test that ALL CAPS words boost urgency"""
        email = "EMERGENCY: We have FLOODING in the basement RIGHT NOW!!!"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "CRITICAL"
        assert result["confidence"] >= 0.95

    # ============ SUBJECT LINE WEIGHT TESTS ============

    def test_subject_line_priority(self, detector):
        """Test that subject line keywords get higher weight"""
        # Subject line has critical keyword
        email_important = "Subject: Water flooding!\nJust some minor questions"
        # Body has critical keyword
        email_less_important = "Subject: General question\nPlease help there's a flood everywhere!"
        
        result_important = detector.detect_urgency(email_important)
        result_less_important = detector.detect_urgency(email_less_important)
        
        # Both should be CRITICAL
        assert result_important["urgency_level"] == "CRITICAL"
        assert result_less_important["urgency_level"] == "CRITICAL"

    # ============ KEYWORD WEIGHT TESTS ============

    def test_weighted_keywords(self, detector):
        """Test that different keywords have different weights"""
        email_critical = "There is water damage everywhere! Burst pipe!"
        email_high = "Need service within 24 hours please"
        
        result_critical = detector.detect_urgency(email_critical)
        result_high = detector.detect_urgency(email_high)
        
        assert result_critical["urgency_level"] == "CRITICAL"
        assert result_high["urgency_level"] == "HIGH"

    # ============ EDGE CASES ============

    def test_empty_email(self, detector):
        """Test handling of empty email"""
        result = detector.detect_urgency("")
        
        assert result["urgency_level"] == "NORMAL"
        assert result["detected_keywords"] == []

    def test_none_email(self, detector):
        """Test handling of None email"""
        result = detector.detect_urgency(None)
        
        assert result["urgency_level"] == "NORMAL"

    def test_multiple_keywords_same_type(self, detector):
        """Test counting multiple keywords of same type"""
        email = "Flooding everywhere! Water damage is flooding the whole house!"
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "CRITICAL"
        assert result["confidence"] > 0.90

    # ============ ESCALATION TESTS ============

    def test_should_escalate_critical(self, detector):
        """Test that CRITICAL should escalate to owner"""
        assert detector.should_escalate_to_owner("CRITICAL") is True

    def test_should_escalate_high(self, detector):
        """Test that HIGH with good confidence should escalate"""
        assert detector.should_escalate_to_owner("HIGH", confidence=0.85) is True

    def test_should_not_escalate_normal(self, detector):
        """Test that NORMAL should not escalate"""
        assert detector.should_escalate_to_owner("NORMAL") is False

    def test_escalate_high_low_confidence(self, detector):
        """Test that HIGH with low confidence might not escalate (depends on threshold)"""
        result = detector.should_escalate_to_owner("HIGH", confidence=0.65)
        # 0.65 < threshold of 0.75
        assert result is False

    # ============ SCORE BREAKDOWN TESTS ============

    def test_score_breakdown_included(self, detector):
        """Test that score breakdown is provided for debugging"""
        email = "Flooding emergency now!"
        result = detector.detect_urgency(email)
        
        assert "score_breakdown" in result
        assert isinstance(result["score_breakdown"], dict)

    def test_score_values_reasonable(self, detector):
        """Test that score values are within reasonable range"""
        email = "This is urgent - no water service!"
        result = detector.detect_urgency(email)
        
        # Confidence should be between 0.0 and 1.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["confidence"], (int, float))

    # ============ REAL-WORLD SCENARIOS ============

    def test_real_scenario_flooded_bathroom(self, detector):
        """Test real-world scenario: flooded bathroom"""
        email = """Subject: URGENT!!! Bathroom flooded!!!

Hello,

My bathroom is flooded with water everywhere. The toilet overflowed and now the whole bathroom is underwater. This is an emergency - I need help IMMEDIATELY!

Please come right now!
John"""
        
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "CRITICAL"
        assert result["confidence"] >= 0.95

    def test_real_scenario_normal_booking(self, detector):
        """Test real-world scenario: normal appointment booking"""
        email = """Subject: Appointment Inquiry

Hi,

I'm interested in booking an appointment for a routine plumbing inspection. I'm flexible with my schedule and can come in anytime next month.

Thanks!
Sarah"""
        
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] == "NORMAL"

    def test_real_scenario_complaint_not_emergency(self, detector):
        """Test real-world scenario: complaint but not emergency"""
        email = """Subject: Poor Service Last Week

Hi,

I wasn't happy with the service last week, but it's not an emergency. When you have a chance, could someone call me to discuss?

Thanks,
Mike"""
        
        result = detector.detect_urgency(email)
        
        assert result["urgency_level"] in ["NORMAL", "HIGH"]
        if result["urgency_level"] == "HIGH":
            # If detected as HIGH, confidence should be moderate (complaint detected)
            assert result["confidence"] < 0.95
