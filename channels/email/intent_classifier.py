import pickle
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
MODEL_FILENAME = "intent_classifier_model.pkl"


def _candidate_model_paths() -> list[Path]:
    """Return likely model locations for local and Docker environments."""
    repo_root = Path(__file__).resolve().parents[2]
    return [
        Path("/model") / MODEL_FILENAME,
        Path("/app/model") / MODEL_FILENAME,
        repo_root / "model" / MODEL_FILENAME,
    ]

class IntentClassifier:
    """
    TF-IDF + Logistic Regression intent classifier.

    Predicts one of 16 intent categories for inbound customer emails:
      price_inquiry, appointment, cancellation, rescheduling, working_hours,
      faq, payment_inquiry, service_request, complaint, feedback,
      warranty_claim, replacement_request, refund_request, upgrade_inquiry,
      bulk_inquiry, other

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
        self.intent_labels = [
            "price_inquiry", "appointment", "cancellation", "rescheduling",
            "working_hours", "faq", "payment_inquiry", "service_request",
            "complaint", "feedback", "warranty_claim", "replacement_request",
            "refund_request", "upgrade_inquiry", "bulk_inquiry", "other",
        ]

        self.sklearn_model = None
        model_paths = _candidate_model_paths()

        for _model_path in model_paths:
            if not _model_path.exists():
                continue

            try:
                with open(_model_path, "rb") as _f:
                    self.sklearn_model = pickle.load(_f)
                logger.info("Loaded TF-IDF+LR intent model from %s", _model_path)
                break
            except (OSError, pickle.PickleError, AttributeError, ValueError, TypeError) as _e:
                logger.warning("Failed to load sklearn intent model at %s: %s", _model_path, _e)

        if self.sklearn_model is None:
            logger.warning(
                "Intent model not found in expected paths: %s — run train_intent_model.py",
                ", ".join(str(path) for path in model_paths),
            )

    def predict_intent(self, email_text: str) -> dict:
        """
        Predict the intent of an email using the trained TF-IDF+LR model.

        Args:
            email_text: Combined subject + body text.

        Returns:
            {"intent": str, "confidence": float, "method": str}
        """
        if self.sklearn_model is None:
            logger.warning("No intent model loaded; defaulting to 'other'")
            return {"intent": "other", "confidence": 0.0, "method": "ml"}

        return self._sklearn_classification(email_text)

    def _sklearn_classification(self, email_text: str) -> dict:
        """Classify with the trained TF-IDF + Logistic Regression pipeline."""
        try:
            proba = self.sklearn_model.predict_proba([email_text])[0]
            classes = self.sklearn_model.classes_
            top_idx = int(proba.argmax())
            return {
                "intent": str(classes[top_idx]),
                "confidence": float(proba[top_idx]),
                "method": "ml",
            }
        except (AttributeError, ValueError, TypeError, IndexError) as exc:
            logger.warning("Sklearn classification failed: %s", exc)
            return {"intent": "other", "confidence": 0.0, "method": "ml"}
