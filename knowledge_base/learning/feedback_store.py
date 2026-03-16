from knowledge_base.kb_store import KBStore
import logging

logger = logging.getLogger(__name__)


class FeedbackStore:
    """
    Stores all owner corrections in database for supervised learning traceability.
    Uses KBStore which writes to PostgreSQL KBFeedback table.
    """

    def __init__(self):
        self.kb_store = KBStore()

    def save(self, feedback_entry: dict, kb_version_id=None):
        """
        Save feedback entry with full context to database.
        
        Args:
            feedback_entry: dict with keys: operation, kb_field, customer_question,
                           owner_correction, service_name, service_description,
                           service_price
            kb_version_id: optional version ID to link feedback to KB version
        """
        operation = feedback_entry.get("operation", "")
        kb_field = feedback_entry.get("kb_field", "")
        customer_question = feedback_entry.get("customer_question", "")
        owner_correction = feedback_entry.get("owner_correction", "")
        
        service_name = feedback_entry.get("service_name", "")
        service_description = feedback_entry.get("service_description", "")
        service_price = feedback_entry.get("service_price", "")
        
        self.kb_store.save_feedback(
            operation=operation,
            kb_field=kb_field,
            customer_question=customer_question,
            owner_correction=owner_correction,
            service_name=service_name,
            service_description=service_description,
            service_price=service_price,
            kb_version_id=kb_version_id
        )
        
        logger.info(f"Feedback saved: {operation} on {kb_field}")
        print("Feedback saved to database.")
