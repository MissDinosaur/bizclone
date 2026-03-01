from transformers import pipeline
import config.config as config


class IntentClassifier:
    """
    NLP-based Intent Detection using Zero-Shot Classification.
    No rule-based logic, no training required.
    """

    def __init__(self):
        self.classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

        # Define BizClone email intents
        self.intent_labels = [
            config.PRICE_INQUERY,
            config.APPOINTMENT,
            config.CANCELLATION,
            config.WORKING_HOUR,
            config.EMERGENCY,
            config.FAQ
        ]

    def predict_intent(self, email_text: str):
        """
        Predict the most likely intent label for an email.
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
