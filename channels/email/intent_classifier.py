from transformers import pipeline
import re
import logging

logger = logging.getLogger(__name__)


APPOINTMENT_SIGNAL_RE = re.compile(
    r"\b(appointment|book|booking|schedule|scheduled|scheduling|slot)\b",
    re.IGNORECASE,
)
TIME_PREFERENCE_RE = re.compile(
    r"\b(next|this|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"morning|afternoon|evening|am|pm)\b",
    re.IGNORECASE,
)
SEND_SOMEONE_RE = re.compile(
    r"\b(are you able to|can you|could you|would you)\b.*\b(send|come)\b",
    re.IGNORECASE,
)


class IntentClassifier:
    """
    NLP-based Intent Detection using Mixed Strategy:
    1. Keyword matching (fast, high precision for common patterns)
    2. Zero-shot classification (handles edge cases and nuanced text)
    3. Confidence-based fallback
    
    16 Intent Categories:
    1. price_inquiry        - Asking about service costs
    2. appointment          - Booking/scheduling a service
    3. cancellation         - Cancel existing appointment completely
    4. rescheduling         - Change appointment to different time
    5. working_hours        - Asking about business hours/availability
    6. faq                  - General questions about services/policies
    7. payment_inquiry      - Invoice, payment method, billing questions
    8. service_request      - Request for specific service (not appointment)
    9. complaint            - Unhappy with existing service
    10. feedback            - Positive feedback or suggestions
    11. warranty_claim      - Warranty or guarantee issue
    12. replacement_request - Need replacement/repair of failed service
    13. refund_request      - Request for money back
    14. upgrade_inquiry     - Upgrade to better service/package
    15. bulk_inquiry        - Corporate/bulk service request
    16. other               - Doesn't fit above categories
    """

    def __init__(self):
        self.classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

        self.intent_labels = [
            "price_inquiry",
            "appointment",
            "cancellation",
            "rescheduling",
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
            "cancellation": "Customer wants to completely cancel existing appointment",
            "rescheduling": "Customer wants to change or reschedule existing appointment to different time",
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
                r"\b(book|schedule)\b.*\b(appointment|slot|available|meeting|service)\b",
                r"\bneed\b.*\b(appointment|booking|slot|consultation)\b",
                r"\b(want to|need|like to|could you|can we|arrange)\s+(schedule|book|make|get|have|an\s+(appointment|meeting|slot))",
                r"\b(when|what time|what day).*\b(available|free|work|possible)\b",
                (
                    r"\b(are you able to|can you|could you|would you)\b"
                    r".*\b(send|come)\b"
                    r".*\b(next|this|on)\b"
                    r".*\b(monday|tuesday|wednesday|thursday|friday|"
                    r"saturday|sunday|week)\b"
                ),
                r"\b(first time|new|initial)\s+(appointment|booking|consultation)\b",
            ],
            "cancellation": [
                r"\b(cancel|no longer need|don't need|won't be|don't want)\b.*\b(appointment|meeting|booking)\b",
                r"\b(can'?t make it|cannot make it|not coming|won't come|not going|forget it|never mind)\b",
                r"\b(please|kindly)\b.{0,30}\bcancel\b",
                r"\b(permanently|completely)\s+(cancel|no need)\b",
            ],
            "rescheduling": [
                r"\b(reschedule|move|delay|change|postpone|shift)\b.*\b(appointment|meeting|slot|booking)\b",
                r"\b(different time|new time|earlier|later|another time)\b.*\b(appointment|slot|booking|time)\b",
                r"\b(what about|how about|can we|could we|would).*\b(different|another|next|later|earlier)\b",
                r"\b(when else|what other time|available)\b.*\b(appointment|slot|booking|time)\b",
                r"\b(too early|too late|doesn't work|inconvenient|doesn't suit)\b",
                r"\b(modify|update|adjust|change)\b.*\b(appointment|booking|time)\b",
                r"\b(existing|current|scheduled|booked)\s+(appointment|meeting|slot).*\b(change|move|reschedule|different)\b",
            ],
            "price_inquiry": [
                r"\b(price|cost|how much|fee|rate|charge|payment|invoice)\b",
                r"\b(how much does|what.*cost|what.*price|quote)\b",
            ],
            "working_hours": [
                r"\b(open|closed|hours|available|when|working time|business hours)\b",
                r"\b(do you|are you|working|open)\s+(on|during)\s+(weekend|sunday|holiday)\b",
            ],
            "service_request": [
                # Requests for specific services or repairs (not appointment booking)
                r"\b(need|require|help|assist|fix|repair|need help|need service)\b.*\b(burst|break|broken|damage|leak|pipe|electrical|water|roof|door|window|appliance)\b",
                r"\b(can you|could you|would you|are you able to)\s+(send|come|help|assist|repair|fix|service)\b",
                r"\b(need|require)\b.*\b(professional|specialist|expert|technician|plumber|electrician|contractor)\b",
                r"\b(burst|broken|damage|leak|flooding|emergency|urgent|immediately)\b.*\b(help|need|send|come)\b",
                r"\b(service request|service needed|service urgent|repair needed|repair urgent)\b",
            ],
            "complaint": [
                # Complaint requires both negative sentiment AND service context (not just generic "problem")
                # This avoids misclassifying "burst pipe problem" as complaint when it's actually a service request
                r"\b(terrible|awful|bad|poor|awful|unhappy|disappointed|frustrated|angry|upset|dissatisfied)\b.*\b(service|appointment|work|job|repair|plumber|electrician|cleaner|your)\b",
                r"\b(service|appointment|work|job|repair|plumber|electrician)\b.*\b(terrible|awful|bad|poor|unhappy|disappointed|frustrated|angry|upset)\b",
                # Explicit complaint phrases
                r"\b(complain|complaint|complaining|unhappy with|disappointed with|not satisfied|poor quality|bad experience|terrible experience)\b",
                # Dissatisfaction with past service (not about missing service)
                r"\b(didn't|didn't|was not|wasn't)\s+(satisfied|happy|pleased|good).+\b(service|appointment|work|job|repair)\b",
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
                "intent": str,           # One of 16 labels
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
        Quick keyword-based intent detection with priority handling.
        
        Higher priority intents (rescheduling, cancellation) are checked first
        to avoid being overridden by lower priority intents (appointment).
        
        Returns:
            Dict with intent, confidence, method or None if no match
        """
        text_lower = text.lower()
        has_appointment_signal = bool(APPOINTMENT_SIGNAL_RE.search(text_lower))
        has_time_preference = bool(TIME_PREFERENCE_RE.search(text_lower))
        has_send_someone_phrase = bool(SEND_SOMEONE_RE.search(text_lower))
        
        # Priority order: check critical intents first
        # Note: complaint removed from priority since its keywords are now very specific
        # and overlap with service_request. order matters: rescheduling/cancellation must be
        # checked before appointment to avoid false positives
        priority_intents = ["rescheduling", "cancellation", "refund_request"]
        regular_intents = [i for i in self.compiled_patterns.keys() if i not in priority_intents]
        
        # Check priority intents first - these should override lower priority matches
        for intent in priority_intents:
            if intent not in self.compiled_patterns:
                continue
            patterns = self.compiled_patterns[intent]
            matches = sum(1 for pattern in patterns if pattern.search(text_lower))
            if matches > 0:
                # Confidence based on number of keyword matches
                # Priority intents get higher base confidence
                confidence = min(0.95, 0.75 + (matches * 0.1))
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "method": "keyword"
                }

        # Strong appointment override: if the email explicitly references appointment
        # and includes timing/scheduling language, prefer appointment over service_request.
        if has_appointment_signal and (has_time_preference or has_send_someone_phrase):
            return {
                "intent": "appointment",
                "confidence": 0.92,
                "method": "keyword"
            }
        
        # Check regular intents if no priority match found
        best_match = None
        best_score = 0
        
        for intent in regular_intents:
            patterns = self.compiled_patterns[intent]
            matches = sum(1 for pattern in patterns if pattern.search(text_lower))
            if matches > 0:
                # Confidence based on number of keyword matches
                confidence = min(0.95, 0.6 + (matches * 0.15))

                # If explicit appointment terms are present, bias toward appointment.
                if intent == "appointment" and has_appointment_signal:
                    confidence = min(0.95, confidence + 0.1)
                if intent == "appointment" and has_time_preference:
                    confidence = min(0.95, confidence + 0.05)

                # Prevent service/complaint intents from overriding explicit appointment requests.
                if intent == "service_request" and has_appointment_signal:
                    confidence = max(0.0, confidence - 0.2)
                if intent == "complaint" and has_appointment_signal:
                    confidence = max(0.0, confidence - 0.25)

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
        # Handle empty or whitespace-only input
        if not email_text or not email_text.strip():
            logger.info("Empty email text provided, defaulting to 'other' intent")
            return {
                "intent": "other",
                "confidence": 0.0,
                "method": "nlp"
            }
        
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
