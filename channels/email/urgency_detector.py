"""
Urgency Detection Module
Separates intent (what user wants) from urgency (how time-sensitive it is).
Uses keyword-based detection + LLM confidence scoring.
"""

import re
from typing import Tuple
import config.logger_config as logger_config


logger = logger_config.get_logger(__name__)

class UrgencyDetector:
    """
    Detects email urgency level independent of intent.
    Urgency levels: CRITICAL, HIGH, NORMAL
    """

    def __init__(self):
        # Create a copy of logger for testing
        self.logger = logger

        # Escalation keywords mapping urgency levels
        self.critical_keywords = [
            # Flooding/Water damage
            r"(flood|burst|burst pipe|water damage|leaking everywhere|pipe break)",
            # Emergency/Urgent words
            r"(emergency|urgent|asap|immediately|now|right now|cannot wait)",
            # Gas safety (if applicable)
            r"(gas leak|carbon monoxide|smell|odor|smoke)",
            # Safety hazard
            r"(danger|hazard|unsafe|risk)",
            # Multiple problems
            r"(multiple|several|all the|everywhere)"
        ]

        self.high_keywords = [
            # Time-bound
            r"(within 24|within today|today|tonight|tomorrow|weekend)",
            # Business impact
            r"(no water|no hot water|cannot use|blocked|stuck)",
            # Complaint/Escalation
            r"(complaint|not satisfied|poor|disappointing|failed)",
            # Repeat issue
            r"(again|already reported|still broken|recurring)"
        ]

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
                "escalation_reason": str
            }
        """
        email_lower = email_text.lower()
        detected_keywords = []
        escalation_reason = ""

        # Check CRITICAL keywords
        for pattern in self.critical_keywords:
            if re.search(pattern, email_lower):
                matches = re.findall(pattern, email_lower)
                detected_keywords.extend([m if isinstance(m, str) else m[0] for m in matches])

        if detected_keywords:
            return {
                "urgency_level": "CRITICAL",
                "confidence": 0.95,
                "detected_keywords": list(set(detected_keywords)),
                "escalation_reason": f"Critical keywords detected: {', '.join(list(set(detected_keywords))[:3])}"
            }

        # Check HIGH keywords
        for pattern in self.high_keywords:
            if re.search(pattern, email_lower):
                matches = re.findall(pattern, email_lower)
                detected_keywords.extend([m if isinstance(m, str) else m[0] for m in matches])

        if len(detected_keywords) >= 2:  # Multiple high-priority indicators
            return {
                "urgency_level": "HIGH",
                "confidence": 0.85,
                "detected_keywords": list(set(detected_keywords)),
                "escalation_reason": f"Multiple urgency indicators: {', '.join(list(set(detected_keywords))[:3])}"
            }

        # Intent-based context rules
        if intent and len(detected_keywords) >= 1:
            if intent in ["appointment", "emergency_service"]:
                return {
                    "urgency_level": "HIGH",
                    "confidence": 0.80,
                    "detected_keywords": list(set(detected_keywords)),
                    "escalation_reason": f"Intent '{intent}' + urgency keywords: {', '.join(list(set(detected_keywords))[:2])}"
                }

        # Default: NORMAL urgency
        return {
            "urgency_level": "NORMAL",
            "confidence": 0.90,
            "detected_keywords": [],
            "escalation_reason": "No urgency indicators detected"
        }

    def should_escalate_to_owner(self, urgency_level: str) -> bool:
        """
        Determine if email should bypass auto-reply and require owner review.

        Args:
            urgency_level: Output from detect_urgency()

        Returns:
            True if owner review needed, False if auto-reply acceptable
        """
        # Always escalate CRITICAL
        if urgency_level == "CRITICAL":
            return True

        # HIGH: escalate if confidence is high (owner can configure threshold)
        if urgency_level == "HIGH":
            return True  # Could make this configurable

        # NORMAL: auto-reply is acceptable
        return False
