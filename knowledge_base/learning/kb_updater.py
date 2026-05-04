import re
import logging
from knowledge_base.kb_store import KBStore

logger = logging.getLogger(__name__)


class KnowledgeBaseUpdater:
    """
    Applies owner corrections into structured KB fields:
    - services pricing
    - policies
    - FAQs
    
    Stores all changes in database via KBStore for full version history.
    """

    def __init__(self):
        self.kb_store = KBStore()

    # -------------------------------
    # MAIN ENTRY POINT
    # -------------------------------
    def apply_update(self, feedback_entry: dict):
        """
        Apply correction to a specific KB item and save to database.
        For Service: merges with existing values, skips update if both fields empty.
        For Policy/FAQ: uses customer_question and owner_correction.
        Returns: (updated_detail, version_number) or (None, None) if no update needed
        """
        kb_field = feedback_entry["kb_field"]
        logger.info(f"Applying update to KB field: {kb_field}")
        logger.info(f"Feedback entry: {feedback_entry}")

        if kb_field == "service":
            service_name = feedback_entry.get("service_name")
            service_description = feedback_entry.get("service_description")
            service_price = feedback_entry.get("service_price")
            item_key = service_name.lower().replace(" ", "_").strip()

            # Check if both fields are empty
            if not service_description and not service_price:
                logger.info(f"Service update skipped: both description and price are empty for '{service_name}'")
                return None, None
            
            # Get current active service to preserve existing values
            current_kb = self.kb_store.get_current_kb()
            current_service = current_kb.get("services", {}).get(item_key, {})
            
            # Merge: use new value if provided, else keep original
            # Pass Python dict directly to SQLAlchemy JSON type (no json.dumps needed)
            detail = {
                "description": service_description if service_description else current_service.get("description", "Service description"),
                "price": service_price if service_price else current_service.get("price", "Contact for pricing")
            }
            change_desc = f"Update {kb_field}: service_name='{service_name}', description={'provided' if service_description else 'kept'}, price={'provided' if service_price else 'kept'}"
            logger.info(f"Service update for '{service_name}': description={'provided' if service_description else 'kept'}, price={'provided' if service_price else 'kept'}")

        elif kb_field == "policy":
            policy_name = feedback_entry.get("policy_name")
            owner_correction = feedback_entry.get("owner_correction")
            logger.info(f"Policy update: policy_name='{policy_name}', owner_correction='{owner_correction}' (type: {type(owner_correction).__name__})")
            item_key = policy_name.lower().replace(" ", "_").replace("?", "").strip()
            detail = owner_correction
            change_desc = f"Update {kb_field}: policy_name='{policy_name}', owner_correction={'provided' if owner_correction else 'kept'}"

        elif kb_field == "faq":
            customer_question = feedback_entry.get("customer_question")
            owner_correction = feedback_entry.get("owner_correction")
            logger.info(f"FAQ update: question='{customer_question}', answer='{owner_correction}'")
            item_key = customer_question.lower().replace("?", "").replace(" ", "_").strip()
            detail = {
                "q": customer_question,
                "a": owner_correction
            }
            change_desc = f"Update {kb_field}: question='{customer_question}', owner_correction={'provided' if owner_correction else 'kept'}"
        else:
            logger.error(f"Unknown kb_field '{kb_field}', defaulting to FAQ")
            
            
        # Save updated KB item to database and activate immediately
        version_number = self.kb_store.save_version(
            kb_field=kb_field,
            item_key=item_key,
            detail=detail,
            change_desc=change_desc,
            updated_by="system",
            activate=True
        )
        
        logger.info(f"KB item {kb_field}[{item_key}] updated as version {version_number}, detail={detail}")
        return detail, version_number

    def apply_insert(self, feedback_entry: dict):
        """
        Insert new entry into a specific KB item and save to database.
        For Service: uses service_name, service_description, service_price
        For Policy: uses policy_name, owner_correction
        For FAQ: uses customer_question, owner_correction
        
        Returns: (detail, version_number)
        """
        kb_field = feedback_entry["kb_field"]
        logger.info(f"Inserting into KB field: {kb_field}")
        logger.info(f"Feedback entry: {feedback_entry}")

        if kb_field == "service":
            service_name = feedback_entry.get("service_name")
            service_description = feedback_entry.get("service_description")
            service_price = feedback_entry.get("service_price")
            item_key = service_name.lower().replace(" ", "_").strip()
            # Pass dict directly (SQLAlchemy JSON type handles serialization)
            detail = {
                "description": service_description,
                "price": service_price
            }
            change_desc = f"Insert {kb_field}: new service: {service_name}"

        elif kb_field == "policy":
            policy_name = feedback_entry.get("policy_name")
            owner_correction = feedback_entry.get("owner_correction")
            logger.info(f"Policy insert: policy_name='{policy_name}', owner_correction='{owner_correction}'")
            item_key = policy_name.lower().replace("?", "").replace(" ", "_").strip()
            # Pass string directly (SQLAlchemy JSON type handles serialization)
            detail = owner_correction
            change_desc = f"Insert {kb_field}: new policy: {policy_name}"

        elif kb_field == "faq":
            customer_question = feedback_entry.get("customer_question")
            owner_correction = feedback_entry.get("owner_correction")
            logger.info(f"FAQ insert: question='{customer_question}', answer='{owner_correction}'")
            item_key = customer_question.lower().replace("?", "").replace(" ", "_").strip()
            # Pass dict directly (SQLAlchemy JSON type handles serialization)
            detail = {
                "q": customer_question,
                "a": owner_correction
            }
            change_desc = f"Insert {kb_field}: new FAQ: {customer_question}"

        else:
            logger.error(f"Unknown kb_field '{kb_field}', defaulting to FAQ insert")
            return None, None

        # Save new KB item to database and activate immediately        
        version_number = self.kb_store.save_version(
            kb_field=kb_field,
            item_key=item_key,
            detail=detail,
            change_desc=change_desc,
            updated_by="system",
            activate=True
        )
        
        logger.info(f"KB item {kb_field}[{item_key}] inserted as version {version_number}")
        return detail, version_number

