"""
Urgency Detection Module
Separates intent (what user wants) from urgency (how time-sensitive it is).
Uses multi-level keyword-based detection + confidence scoring.
"""

import re
from typing import Tuple, Set
import config.logger_config as logger_config


logger = logger_config.get_logger(__name__)


class UrgencyDetector:
    """
    Detects email urgency level independent of intent.
    Urgency levels: CRITICAL, HIGH, NORMAL
    
    Improvements:
    - Word boundary matching to avoid false positives
    - Dynamic confidence scoring based on keyword weight and frequency
    - Negation detection (e.g., "not urgent")
    - Format and punctuation analysis
    - Subject line gets higher weight than body
    - Intent-aware escalation
    """

    def __init__(self):
        # Create a copy of logger for testing
        self.logger = logger

        # CRITICAL keywords: Safety/flooding/immediate danger
        self.critical_keywords = {
            # Flooding/Water damage (HIGH CONFIDENCE) - match variations like flood, flooding, flooded
            r"\b(flood\w*|burst\s+pipe|water\s+damage|leak.*everywhere|pipe\s+break|burst\s+water|gushing|overflowing)\b": 1.0,
            # Emergency/Urgent (HIGH CONFIDENCE)
            r"\b(emergency|urgent|asap|immediately|right\s+now|cannot\s+wait)\b": 0.95,
            # Gas safety (CRITICAL)
            r"\b(gas\s+leak|carbon\s+monoxide|smell.*gas|odor.*gas|smoke.*smell)\b": 1.0,
            # Safety hazard (CRITICAL)
            r"\b(danger|hazard|unsafe|risk|life\s+threatening)\b": 0.95,
            # Multiple critical issues
            r"\b(multiple\s+problems|everywhere|all\s+broken|total\s+failure)\b": 0.90,
        }

        # HIGH keywords: Time-bound or business-impacting
        self.high_keywords = {
            # Strict time bounds (HIGH)
            r"\b(within\s+24|within\s+hours|within\s+today|today|tonight|tomorrow|this\s+weekend|asap)\b": 0.85,
            # Service unavailable (HIGH)
            r"\b(no\s+water|no\s+hot\s+water|cannot\s+use|block\w*|stuck|broken|stop.*working)\b": 0.80,
            # Complaint/Escalation (MEDIUM-HIGH)
            r"\b(complaint|very\s+unhappy|not\s+satisfied|poor\s+service|disappointing|failed|unacceptable)\b": 0.75,
            # Repeat issues (MEDIUM-HIGH)
            r"\b(again|already\s+reported|still\s+broken|happen.*again|recur|third\s+time)\b": 0.75,
            # Waiting for service (MEDIUM)
            r"\b(waiting|been\s+waiting|how\s+long|when\s+can|need\s+soon|can\s+you\s+come)\b": 0.70,
            # Payment/billing related urgency
            r"\b(overdue|must\s+pay|urgent\s+payment)\b": 0.70,
        }

        # Intensity indicators (modifiers that boost confidence)
        self.intensity_markers = {
            r"\b(very|extremely|really|so|absolutely|definitely)\b": 0.15,  # Boost amount
            r"!!!+": 0.20,  # Multiple exclamation marks
            r"\?\?\?+": 0.15,  # Multiple question marks
            r"\b[A-Z]{3,}\b": 0.10,  # ALL CAPS words
        }

        # Negation patterns to check (reduce confidence if found)
        self.negation_patterns = [
            r"\b(not|no|doesn't|don't|can't|won't|never)\s+\w+\s+(urgent|emergency|critical|asap)",
            r"\b(can\s+wait|not\s+urgent|not\s+emergency|not\s+critical)",
        ]

    def _contains_negation_for_urgency(self, text: str) -> bool:
        """Check if text contains negation of urgency."""
        text_lower = text.lower()
        for pattern in self.negation_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _count_matching_keywords(self, text: str, keyword_dict: dict) -> Tuple[int, float, list]:
        """
        Count matches and calculate weighted confidence.
        
        Returns:
            (match_count, weighted_confidence, matched_keywords)
        """
        text_lower = text.lower()
        matched_keywords = []
        total_weight = 0.0
        matches = 0

        for pattern, weight in keyword_dict.items():
            found = re.findall(pattern, text_lower)
            if found:
                matches += len(found)
                total_weight += weight * len(found)
                # Extract first match for display
                matched_keywords.append(found[0] if isinstance(found[0], str) else found[0][0])

        return matches, total_weight, matched_keywords

    def _analyze_format_intensity(self, email_text: str) -> float:
        """
        Analyze formatting for intensity indicators.
        Returns boost amount (0.0 - 0.3)
        """
        boost = 0.0

        # Check for multiple exclamation/question marks
        if "!!!" in email_text:
            boost += 0.15
        elif "!!" in email_text:
            boost += 0.08

        if "???" in email_text:
            boost += 0.10
        elif "??" in email_text:
            boost += 0.05

        # Count all-caps words (excluding very short words)
        all_caps_words = len(re.findall(r"\b[A-Z]{3,}\b", email_text))
        if all_caps_words >= 3:
            boost += 0.15
        elif all_caps_words >= 1:
            boost += 0.05

        return min(boost, 0.30)  # Cap the boost

    def _analyze_subject_and_body(self, email_text: str) -> Tuple[str, str]:
        """
        Split email into subject (first line) and body.
        Subject line is typically the first line or before first newline.
        """
        lines = email_text.split("\n", 1)
        subject = lines[0] if lines else ""
        body = lines[1] if len(lines) > 1 else ""
        return subject, body

    def detect_urgency(self, email_text: str, intent: str = None) -> dict:
        """
        Detect urgency level from email content.
        Args:
            email_text: Email subject + body
            intent: Optional intent to apply context-specific rules
        Returns:
            {
                "urgency_level": "CRITICAL" | "HIGH" | "NORMAL",
                "confidence": float,  # 0.0-1.0
                "detected_keywords": [list],
                "escalation_reason": str,
                "score_breakdown": dict  # Debug info
            }
        """
        if not email_text or not isinstance(email_text, str):
            return {
                "urgency_level": "NORMAL",
                "confidence": 1.0,
                "detected_keywords": [],
                "escalation_reason": "Empty or invalid email text",
                "score_breakdown": {"empty_input": True}
            }

        # Check for negation of urgency (rule out false positives)
        if self._contains_negation_for_urgency(email_text):
            return {
                "urgency_level": "NORMAL",
                "confidence": 0.95,
                "detected_keywords": [],
                "escalation_reason": "Negation of urgency detected",
                "score_breakdown": {"negation_detected": True}
            }

        # Split subject and body for weighted analysis
        subject, body = self._analyze_subject_and_body(email_text)
        
        # Analyze CRITICAL keywords
        crit_count_subject, crit_weight_subject, crit_keywords_subject = \
            self._count_matching_keywords(subject, self.critical_keywords)
        crit_count_body, crit_weight_body, crit_keywords_body = \
            self._count_matching_keywords(body, self.critical_keywords)

        # Subject line gets 2x weight
        total_crit_weight = (crit_weight_subject * 2.0) + crit_weight_body
        total_crit_matches = crit_count_subject + crit_count_body
        
        # Analyze format intensity
        format_boost = self._analyze_format_intensity(email_text)

        if total_crit_matches > 0:
            # Calculate confidence with format boost
            base_confidence = min(0.95 + (total_crit_weight / 10.0), 1.0)
            confidence = min(base_confidence + format_boost, 1.0)
            
            detected_keywords = list(set(crit_keywords_subject + crit_keywords_body))
            return {
                "urgency_level": "CRITICAL",
                "confidence": round(confidence, 2),
                "detected_keywords": detected_keywords[:5],
                "escalation_reason": f"CRITICAL: {', '.join(detected_keywords[:3])}",
                "score_breakdown": {
                    "critical_matches": total_crit_matches,
                    "critical_weight": round(total_crit_weight, 2),
                    "format_boost": round(format_boost, 2),
                    "final_confidence": round(confidence, 2)
                }
            }

        # Analyze HIGH keywords
        high_count_subject, high_weight_subject, high_keywords_subject = \
            self._count_matching_keywords(subject, self.high_keywords)
        high_count_body, high_weight_body, high_keywords_body = \
            self._count_matching_keywords(body, self.high_keywords)

        # Subject line gets 1.5x weight
        total_high_weight = (high_weight_subject * 1.5) + high_weight_body
        total_high_matches = high_count_subject + high_count_body

        # Intent-based boost for certain intents
        intent_boost = 0.0
        intent_reason = ""
        if intent and intent in ["emergency_service", "appointment", "service_request"]:
            intent_boost = 0.10
            intent_reason = f" + intent '{intent}'"

        if total_high_matches >= 2 or total_high_weight >= 1.0:
            # Multiple high-priority indicators
            base_confidence = min(0.80 + (total_high_weight / 15.0), 0.95)
            confidence = min(base_confidence + format_boost + intent_boost, 1.0)
            
            detected_keywords = list(set(high_keywords_subject + high_keywords_body))
            return {
                "urgency_level": "HIGH",
                "confidence": round(confidence, 2),
                "detected_keywords": detected_keywords[:5],
                "escalation_reason": f"HIGH: {', '.join(detected_keywords[:3])}{intent_reason}",
                "score_breakdown": {
                    "high_matches": total_high_matches,
                    "high_weight": round(total_high_weight, 2),
                    "format_boost": round(format_boost, 2),
                    "intent_boost": round(intent_boost, 2),
                    "final_confidence": round(confidence, 2)
                }
            }

        if total_high_matches >= 1 and intent and intent in ["emergency_service", "appointment"]:
            # Single keyword + emergency-related intent
            base_confidence = min(0.75 + intent_boost, 0.90)
            confidence = min(base_confidence + format_boost, 1.0)
            
            detected_keywords = list(set(high_keywords_subject + high_keywords_body))
            return {
                "urgency_level": "HIGH",
                "confidence": round(confidence, 2),
                "detected_keywords": detected_keywords[:3],
                "escalation_reason": f"Intent '{intent}' + urgency indicators{intent_reason}",
                "score_breakdown": {
                    "high_matches": total_high_matches,
                    "intent_boost": round(intent_boost, 2),
                    "format_boost": round(format_boost, 2),
                    "final_confidence": round(confidence, 2)
                }
            }

        # Default: NORMAL urgency
        return {
            "urgency_level": "NORMAL",
            "confidence": 0.90,
            "detected_keywords": [],
            "escalation_reason": "No urgency indicators detected",
            "score_breakdown": {
                "critical_matches": 0,
                "high_matches": total_high_matches,
                "final_confidence": 0.90
            }
        }

    def should_escalate_to_owner(self, urgency_level: str, confidence: float = None) -> bool:
        """
        Determine if email should bypass auto-reply and require owner review.

        Args:
            urgency_level: Output from detect_urgency()
            confidence: Confidence score (optional, for threshold-based decisions)

        Returns:
            True if owner review needed, False if auto-reply acceptable
        """
        # Always escalate CRITICAL
        if urgency_level == "CRITICAL":
            return True

        # HIGH: escalate if confidence is above threshold (configurable)
        if urgency_level == "HIGH":
            threshold = 0.75
            if confidence is not None:
                return confidence >= threshold
            return True

        # NORMAL: auto-reply is acceptable
        return False
