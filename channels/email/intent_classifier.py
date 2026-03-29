from transformers import pipeline
import config.config as cfg


class IntentClassifier:
    """
    NLP-based Intent Detection using Zero-Shot Classification.
    
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

    def predict_intent(self, email_text: str):
        """
        Predict the most likely intent label for an email.        
        Args:
            email_text: Email subject + body           
        Returns:
            {
                "intent": str,           # One of 15 labels
                "confidence": float      # 0.0-1.0
            }
        """

        result = self.classifier(
            email_text,
            candidate_labels=self.intent_labels
        )

        top_intent = result["labels"][0]
        confidence = result["scores"][0]

        return {
            "intent": top_intent,
            "confidence": confidence
        }
