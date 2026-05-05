## Old Intent_classifier.py
from transformers import pipeline
import pickle
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LM_MODEL_PATH = Path("/model/intent_classifier_model.pkl")
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
    embedding-based Intent Detection using Mixed Strategy:
    1. Keyword matching (fast, high precision for common patterns)
    2. all-MiniLM-L6-v2 classification (handles edge cases and nuanced text)
    3. Confidence-based fallback

    """

    def __init__(self):
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
            "payment_inquiry": [
                r"\b(invoice|receipt|billing|payment\s+method|credit\s+card|bank\s+transfer|deposit|balance\s+due)\b",
                r"\b(how|what)\b.*\b(pay|payment|billing)\b",
                r"\b(payment|billing)\s+(method|option|process|works|arrangement)\b",
                r"\b(pay|payment)\s+(by|with|via|online)\b",
                r"\b(when\s+is|how\s+much\s+is)\b.*\b(balance|deposit|payment|final\s+payment)\b",
                r"\b(which\s+payment|accept|accepted)\b.*\b(method|option|card|transfer|cash)\b",
            ],
            "feedback": [
                r"\b(great|excellent|fantastic|wonderful|amazing|outstanding|brilliant|superb)\s+(service|work|job|experience|visit|repair|plumber|technician)\b",
                r"\b(thank|thanks)\b.*\b(for\s+the|for\s+your)\b.*\b(service|work|job|repair|visit|help)\b",
                r"\b(very|really|extremely|so)\s+(happy|pleased|satisfied|impressed|delighted)\b",
                r"\b(happy|pleased|satisfied|impressed)\s+with\b.*\b(service|work|repair|visit|technician|plumber)\b",
                r"\b(positive\s+feedback|pass\s+on\s+my\s+thanks|well\s+done|great\s+job|good\s+job)\b",
                r"\bjust\s+wanted\s+to\s+(say|share|express)\b.*\b(thank|thanks|appreciate|grateful)\b",
                r"\b(was|were)\s+(really|very|so)\s+(happy|pleased|satisfied|impressed)\s+with\b",
                r"\b(compliment|appreciate|commend|praise)\b.*\b(service|work|technician|plumber|team)\b",
            ],
            "warranty_claim": [
                r"\b(warranty|guarantee)\s+(claim|issue|request|problem|period)\b",
                r"\b(under\s+warranty|under\s+guarantee|covered\s+under|still\s+under)\b",
                r"\b(make\s+a\s+warranty|make\s+a\s+claim|warranty\s+claim|guarantee\s+claim)\b",
                r"\b(same\s+(fault|problem|issue))\b.*\b(returned|back|again|reoccurred)\b",
                r"\b(fault|problem|issue)\b.*\b(returned|back\s+again|reoccurred)\b.*\b(warranty|guarantee)\b",
                r"\b(repaired|fixed|serviced)\b.*\b(weeks?|months?)\b.*\b(ago|back)\b.*\b(same|again|returned)\b",
                r"\b(should\s+(still\s+)?be\s+(covered|under)\b.*\b(warranty|guarantee))\b",
            ],
            "replacement_request": [
                r"\b(replacement|replace)\b.*\b(unit|part|component|faucet|valve|pipe|shower|toilet|boiler|heater)\b",
                r"\b(full\s+replacement|complete\s+replacement|arrange\s+a\s+replacement)\b",
                r"\b(request\s+a\s+replacement|need\s+a\s+replacement|want\s+a\s+replacement|like\s+a\s+replacement)\b",
                r"\b(instead\s+of\s+(another|a)\s+(repair|fix|temporary))\b",
                r"\b(rather\s+than\s+(another|a)\s+(repair|fix|temporary))\b",
                r"\b(malfunctioning|keeps\s+(dripping|leaking|failing|breaking))\b.*\b(replacement|replace)\b",
                r"\b(failed\s+again|not\s+working\s+again|broken\s+again)\b.*\b(replacement|replace|new)\b",
            ],
            "upgrade_inquiry": [
                r"\b(upgrade|upgrading)\b.*\b(service|plan|system|package|tier|maintenance|contract)\b",
                r"\b(better|advanced|higher.tier|premium|superior|top.tier)\s+(service|plan|system|package|option|maintenance)\b",
                r"\b(upgrade\s+options|upgrade\s+packages|upgrade\s+plan|upgrade\s+service)\b",
                r"\b(thinking\s+about\s+upgrading|interested\s+in\s+upgrading|want\s+to\s+upgrade|considering\s+upgrading)\b",
                r"\b(higher.tier|higher\s+tier|top.tier|priority\s+support|priority\s+service|enhanced\s+plan)\b",
                r"\b(can\s+we\s+upgrade|could\s+we\s+upgrade|would\s+like\s+to\s+upgrade|move\s+to\s+a\s+higher)\b",
                r"\b(differences\s+between\s+packages|package\s+differences|tier\s+differences)\b",
            ],
            "bulk_inquiry": [
                r"\b(bulk|corporate|commercial|multiple\s+units|multiple\s+properties|several\s+buildings|several\s+properties)\b",
                r"\b(bulk\s+service|bulk\s+pricing|corporate\s+account|corporate\s+inquiry|bulk\s+agreement|bulk\s+contract)\b",
                r"\b(apartment\s+complex|office\s+buildings?|commercial\s+property|industrial\s+estate|managed\s+properties)\b",
                r"\b(manage|managing|oversee|property\s+manager|facility\s+manager)\b.*\b(multiple|several|various|number\s+of)\b.*\b(unit|building|property|site)\b",
                r"\b(bulk\s+(discount|rate|pricing|deal|contract|agreement|arrangement))\b",
                r"\b(service\s+agreement|maintenance\s+contract)\b.*\b(multiple|several|many|all)\b",
            ],
            "faq": [
                r"\b(do\s+you|are\s+you|can\s+you|would\s+you)\s+(offer|provide|cover|have|accept|service|install|replace|supply|support)\b",
                r"\b(do\s+you\s+offer|do\s+you\s+provide|do\s+you\s+have|do\s+you\s+accept|do\s+you\s+work)\b",
                r"\b(senior\s+discount|repeat\s+customer|loyalty\s+discount|student\s+discount|pensioner\s+discount)\b",
                r"\b(is\s+there\s+(an?\s+)?(additional\s+)?fee|is\s+there\s+a\s+charge|is\s+there\s+a\s+cost)\b",
                r"\b(what\s+(services|types|kinds|areas|zones|regions)|which\s+services\s+do\s+you)\b",
                r"\b(how\s+long\s+does|how\s+long\s+will\s+it|how\s+soon\s+can|how\s+quickly\s+can)\b",
                r"\b(general\s+question|quick\s+question|just\s+wondering|just\s+wanted\s+to\s+know|curious\s+about)\b",
                r"\b(do\s+you\s+also|do\s+you\s+still|do\s+you\s+currently)\b",
            ],
        }

        # Compile regex patterns for efficiency
        self.compiled_patterns = {}
        for intent, patterns in self.keyword_patterns.items():
            self.compiled_patterns[intent] = [re.compile(p, re.IGNORECASE) for p in patterns]

        # Load trained sklearn model if available (primary ML fallback before BART)
        self.sklearn_model = None
        _model_path = LM_MODEL_PATH
        if _model_path.exists():
            try:
                with open(_model_path, "rb") as _f:
                    self.sklearn_model = pickle.load(_f)
                logger.info("Loaded trained sklearn intent model from %s", _model_path)
            except Exception as _e:
                logger.warning("Failed to load sklearn intent model: %s", _e)

    def predict_intent(self, email_text: str):
        """
        Predict intent using mixed strategy:
        1. Try keyword matching first (fast, high precision)
        2. Fall back to embedding model if no strong keyword match
        """

        # Step 1: High-confidence keyword matching (fast, deterministic)
        keyword_result = self._keyword_matching(email_text)
        if keyword_result and keyword_result["confidence"] >= 0.85:
            logger.info("Intent via keyword (high conf): %s (%.2f)", keyword_result["intent"], keyword_result["confidence"])
            return keyword_result

        # Step 2: Trained sklearn model (domain-specific, much faster than BART)
        if self.sklearn_model is not None:
            ml_result = self._sklearn_classification(email_text)
            logger.info("Intent via sklearn ML: %s (%.2f)", ml_result["intent"], ml_result["confidence"])
            # If ML is confident, prefer it; but let a strong keyword override
            if ml_result["confidence"] >= 0.60:
                if keyword_result and keyword_result["confidence"] > ml_result["confidence"]:
                    return keyword_result
                return ml_result

        # Step 3: Medium-confidence keyword fallback
        if keyword_result and keyword_result["confidence"] > 0.65:
            logger.info("Intent via keyword (med conf): %s (%.2f)", keyword_result["intent"], keyword_result["confidence"])
            return keyword_result

        return ml_result

    def _sklearn_classification(self, email_text: str):
        """
        Classify intent using the trained TF-IDF + Logistic Regression model.
        """
        try:
            proba = self.sklearn_model.predict_proba([email_text])[0]
            classes = self.sklearn_model.classes_
            top_idx = int(proba.argmax())
            return {
                "intent": str(classes[top_idx]),
                "confidence": float(proba[top_idx]),
                "method": "ml",
            }
        except Exception as exc:
            logger.warning("Sklearn classification failed: %s", exc)
            return {"intent": "other", "confidence": 0.0, "method": "ml"}

    def _keyword_matching(self, text: str):
        """
        Quick keyword-based intent detection with priority handling.
        Returns:
            Dict with intent, confidence, method or None if no match
        """
        text_lower = text.lower()
        has_appointment_signal = bool(APPOINTMENT_SIGNAL_RE.search(text_lower))
        has_time_preference = bool(TIME_PREFERENCE_RE.search(text_lower))
        has_send_someone_phrase = bool(SEND_SOMEONE_RE.search(text_lower))

        # Priority order: check critical intents first
        # Note: order matters: rescheduling/cancellation must be
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

