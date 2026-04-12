from transformers import pipeline
import re
import logging

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    NLP-based Intent Detection using Mixed Strategy:
    1. Keyword matching (fast, high precision for common patterns)
    2. Zero-shot classification (handles edge cases and nuanced text)
    3. Confidence-based fallback
    
    15 Intent Categories (removed EMERGENCY - now handled by UrgencyDetector):
    1. price_inquiry        - Asking about service costs
    2. appointment          - Booking/scheduling a service
    3. cancellation         - Cancel existing appointment
    4. working_hours        - Asking about business hours/availability
    5. faq                  - General questions about services/policies
    6. payment_inquiry      - Invoice, payment method, billing questions
    7. service_request      - Request for specific service (not appointment)
    8. complaint            - Unhappy with existing service
    9. feedback             - Positive feedback or suggestions
    10. warranty_claim      - Warranty or guarantee issue
    11. replacement_request - Need replacement/repair of failed service
    12. refund_request      - Request for money back
    13. upgrade_inquiry     - Upgrade to better service/package
    14. bulk_inquiry        - Corporate/bulk service request
    15. other               - Doesn't fit above categories
    """

    def __init__(self):
        self.classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

        self.intent_labels = [
            "price_inquiry",
            "appointment",
            "cancellation",
            "working_hours",
            "faq",
            "payment_inquiry",
            "service_request",
            "complaint",
            "feedback",
            "warranty_claim",
            "replacement_request",
            "refund_request",
            "upgrade_inquiry",
            "bulk_inquiry",
            "other"
        ]
        
        # Candidate sentences that better describe each intent
        # These are more descriptive than just labels
        self.intent_descriptions = {
            "price_inquiry": "Customer is asking about pricing, costs, or rates",
            "appointment": "Customer wants to schedule, book, or make an appointment",
            "cancellation": "Customer wants to cancel, postpone, or reschedule existing appointment",
            "working_hours": "Customer is asking about business hours, availability, or when we work",
            "faq": "Customer has general questions about services or company policies",
            "payment_inquiry": "Customer is asking about invoices, payment methods, or billing",
            "service_request": "Customer is requesting a specific service or repair",
            "complaint": "Customer is complaining or expressing dissatisfaction",
            "feedback": "Customer is giving positive feedback or suggestions",
            "warranty_claim": "Customer is making a warranty claim or guarantee issue",
            "replacement_request": "Customer wants replacement or repair of failed service",
            "refund_request": "Customer is requesting a refund or money back",
            "upgrade_inquiry": "Customer wants to upgrade service or package",
            "bulk_inquiry": "Customer is making a corporate or bulk service inquiry",
            "other": "Does not fit any of the above categories"
        }
        
        # Keyword patterns for quick matching (higher priority)
        # Format: (intent, keyword_patterns, confidence_boost)
        self.keyword_patterns = {
            "appointment": [
                r"\b(book|schedule|appointment|slot|available|when|availability|can you come|please come)\b",
                r"\b(want to|need|like to|could you|can we|arrange)\s+(schedule|book|make|get|have)",
                r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|this week|next week)\b.*\b(available|possible|work)\b",
            ],
            "cancellation": [
                r"\b(cancel|postpone|reschedule|move|delay|change.*appointment)\b",
                r"\b(can't|cannot|no longer|won't work|not available)\b.*\b(appointment|meeting|slot)\b",
            ],
            "price_inquiry": [
                r"\b(price|cost|how much|fee|rate|charge|payment|invoice)\b",
                r"\b(how much does|what.*cost|what.*price|quote)\b",
            ],
            "working_hours": [
                r"\b(open|closed|hours|available|when|working time|business hours)\b",
                r"\b(do you|are you|working|open)\s+(on|during)\s+(weekend|sunday|holiday)\b",
            ],
            "complaint": [
                r"\b(terrible|awful|bad|poor|unhappy|disappointed|problem|issue|wrong|broken)\b",
                r"\b(complain|complaint|frustrated|angry|upset)\b",
            ],
            "refund_request": [
                r"\b(refund|money back|reimburse|return money|compensation)\b",
                r"\b(want.*back|get.*back|return.*money)\b",
            ],
        }
        
        # Compile regex patterns for efficiency
        self.compiled_patterns = {}
        for intent, patterns in self.keyword_patterns.items():
            self.compiled_patterns[intent] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def predict_intent(self, email_text: str):
        """
        Predict intent using mixed strategy:
        1. Try keyword matching first (fast, high precision)
        2. Fall back to zero-shot if no strong keyword match
        
        Args:
            email_text: Email subject + body           
        Returns:
            {
                "intent": str,           # One of 15 labels
                "confidence": float,     # 0.0-1.0
                "method": str            # "keyword" or "nlp"
            }
        """
        
        # Step 1: Try keyword matching
        keyword_result = self._keyword_matching(email_text)
        if keyword_result and keyword_result["confidence"] > 0.7:
            logger.info(f"Intent detected via keyword: {keyword_result['intent']} (confidence: {keyword_result['confidence']:.2f})")
            return keyword_result
        
        # Step 2: Use zero-shot classification with descriptive sentences
        nlp_result = self._zero_shot_classification(email_text)
        
        # Step 3: If NLP confidence is low and we have keyword match, consider keyword result
        if keyword_result and nlp_result["confidence"] < 0.6:
            if keyword_result["confidence"] > nlp_result["confidence"]:
                logger.info(f"Using keyword match over low-confidence NLP: {keyword_result['intent']}")
                return keyword_result
        
        logger.info(f"Intent detected via NLP: {nlp_result['intent']} (confidence: {nlp_result['confidence']:.2f})")
        return nlp_result
    
    def _keyword_matching(self, text: str):
        """
        Quick keyword-based intent detection.
        
        Returns:
            Dict with intent, confidence, method or None if no match
        """
        text_lower = text.lower()
        best_match = None
        best_score = 0
        
        for intent, patterns in self.compiled_patterns.items():
            matches = sum(1 for pattern in patterns if pattern.search(text_lower))
            if matches > 0:
                # Confidence based on number of keyword matches
                confidence = min(0.95, 0.6 + (matches * 0.15))
                if confidence > best_score:
                    best_score = confidence
                    best_match = {
                        "intent": intent,
                        "confidence": confidence,
                        "method": "keyword"
                    }
        
        return best_match
    
    def _zero_shot_classification(self, email_text: str):
        """
        Zero-shot classification using descriptive sentences.
        
        Returns:
            Dict with intent, confidence, method
        """
        # Use descriptions instead of just labels for better classification
        candidate_descriptions = [self.intent_descriptions[label] for label in self.intent_labels]
        
        result = self.classifier(
            email_text,
            candidate_labels=candidate_descriptions,
            hypothesis_template="This customer email is about: {}",
            multi_class=False
        )
        
        # Map description back to intent label
        top_description = result["labels"][0]
        # Find which intent this description belongs to
        for intent, desc in self.intent_descriptions.items():
            if desc == top_description:
                return {
                    "intent": intent,
                    "confidence": result["scores"][0],
                    "method": "nlp"
                }
        
        # Fallback (shouldn't reach here)
        return {
            "intent": "other",
            "confidence": 0.5,
            "method": "nlp"
        }
