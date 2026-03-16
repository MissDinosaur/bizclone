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
        Apply correction into the correct KB section and save to database.
        Returns: (updated_kb, version_number)
        """
        kb_field = feedback_entry["kb_field"]
        logger.info(f"Applying update to KB field: {kb_field}")

        kb = self.kb_store.get_current_kb()

        if kb_field == "service":
            service_name = feedback_entry.get("service_name")
            service_description = feedback_entry.get("service_description")
            service_price = feedback_entry.get("service_price")
            kb = self._update_service(kb, service_name, service_description, service_price)

        elif kb_field == "policy":
            customer_question = feedback_entry["customer_question"]
            owner_correction = feedback_entry["owner_correction"]
            correction_text = f"{customer_question} - {owner_correction}".strip()
            kb = self._update_policy(kb, correction_text)

        elif kb_field == "faq":
            customer_question = feedback_entry["customer_question"]
            owner_correction = feedback_entry["owner_correction"]
            correction_text = f"{customer_question} - {owner_correction}".strip()
            kb = self._update_faq(kb, correction_text)

        else:
            logger.warning(f"Unknown kb_field '{kb_field}', defaulting to FAQ")
            logger.info("Unknown kb_field, fallback to FAQ append.")
            customer_question = feedback_entry["customer_question"]
            owner_correction = feedback_entry["owner_correction"]
            correction_text = f"{customer_question} - {owner_correction}".strip()
            kb = self._update_faq(kb, correction_text)

        # Save updated KB to database and activate immediately
        change_desc = f"Update {kb_field}: {feedback_entry['customer_question'][:50]}"
        if kb_field == "service":
            change_desc = f"Update service {feedback_entry.get('service_name')[:50]} and its details."
        version_number = self.kb_store.save_version(
            kb_data=kb,
            change_desc=change_desc,
            updated_by="system",
            activate=True  # Create and activate in one atomic operation
        )
        
        logger.info(f"KB updated and activated as version {version_number}")
        return kb, version_number

    def apply_insert(self, feedback_entry: dict):
        """
        Insert new entry into the correct KB section and save to database.
        
        Returns: (updated_kb, version_number)
        """
        kb_field = feedback_entry["kb_field"]
        logger.info(f"Inserting into KB field: {kb_field}")

        kb = self.kb_store.get_current_kb()

        if kb_field == "service":
            service_name = feedback_entry.get("service_name")
            service_description = feedback_entry.get("service_description")
            service_price = feedback_entry.get("service_price")
            kb = self._insert_service(kb, service_name, service_description, service_price)

        elif kb_field == "policy":
            customer_question = feedback_entry["customer_question"]
            owner_correction = feedback_entry["owner_correction"]
            kb = self._insert_policy(kb, customer_question, owner_correction)

        elif kb_field == "faq":
            customer_question = feedback_entry["customer_question"]
            owner_correction = feedback_entry["owner_correction"]
            kb = self._insert_faq(kb, customer_question, owner_correction)

        else:
            logger.warning(f"Unknown kb_field '{kb_field}', defaulting to FAQ insert")
            customer_question = feedback_entry["customer_question"]
            owner_correction = feedback_entry["owner_correction"]
            kb = self._insert_faq(kb, customer_question, owner_correction)

        # Save updated KB to database and activate immediately
        change_desc = f"Insert {kb_field}: {feedback_entry['customer_question'][:50]}"
        if kb_field == "service":
            change_desc = f"Insert service {feedback_entry.get('service_name')[:50]} and its details."
        version_number = self.kb_store.save_version(
            kb_data=kb,
            change_desc=change_desc,
            updated_by="system",
            activate=True  # Create and activate in one atomic operation
        )
        
        logger.info(f"KB updated and activated as version {version_number}")
        print(f"Knowledge Base updated successfully as version {version_number}.")
        return kb, version_number

    # -------------------------------
    # SERVICE UPDATE
    # -------------------------------
    def _update_service(self, kb, service_name: str, service_description: str = None, service_price: str = None):
        """
        Update existing service with new description and/or price.
        
        Args:
            service_name: The service key (e.g., "emergency_plumbing")
            service_description: Updated description (optional)
            service_price: Updated price (optional)
        """
        services = kb.get("services", {})
        
        service_key = service_name.lower().replace(" ", "_").strip()
        
        if service_key not in services:
            logger.info(f"Service '{service_key}' not found. Creating new entry.")
            services[service_key] = {
                "description": service_description or "Service description",
                "price": service_price or "Contact for pricing"
            }
        else:
            logger.info(f"Updating service '{service_key}'")
            if service_description:
                services[service_key]["description"] = service_description
            if service_price:
                services[service_key]["price"] = service_price
        
        kb["services"] = services
        return kb

    # -------------------------------
    # POLICY UPDATE
    # -------------------------------
    def _update_policy(self, kb, correction_text):
        """
        Update policies section.
        Example:
        "Cancellations are free up to 12 hours in advance."
        """

        if "cancel" in correction_text.lower():
            kb["policies"]["cancellation"] = correction_text
            print("Cancellation policy updated.")

        elif "payment" in correction_text.lower():
            kb["policies"]["payment_methods"] = correction_text
            print("Payment policy updated.")

        else:
            print("Policy update stored as general policy note.")
            kb["policies"]["general_update"] = correction_text

        return kb

    # -------------------------------
    # FAQ UPDATE
    # -------------------------------
    def _update_faq(self, kb, correction_text):
        """
        Default fallback: store correction into FAQs.
        """

        kb["faqs"].append({
            "q": "Owner update",
            "a": correction_text
        })

        print("Stored correction as FAQ entry.")

        return kb

    # -------------------------------
    # SERVICE INSERT
    # -------------------------------
    def _insert_service(self, kb, service_name: str, service_description: str, service_price: str):
        """
        Insert a new service with full details.
        
        Args:
            service_name: Service name/key (e.g., "roof_leak_repair")
            service_description: Description of the service
            service_price: Price (e.g., "€140 per hour")
        """
        services = kb.get("services", {})

        # Normalize service key
        service_key = service_name.lower().replace(" ", "_").strip()

        # Create new service entry
        services[service_key] = {
            "description": service_description,
            "price": service_price
        }

        kb["services"] = services
        print(f"New service '{service_key}' added with price: {service_price}")

        return kb

    # -------------------------------
    # POLICY INSERT
    # -------------------------------
    def _insert_policy(self, kb, question: str, details: str):
        """
        Insert a new policy entry.
        
        Format expected:
        - question: "Policy name (e.g., Warranty policy)"
        - details: "Full policy text"
        """
        policies = kb.get("policies", {})

        # Create policy key from question
        policy_key = question.lower().replace("?", "").replace(" ", "_").strip()
        
        policies[policy_key] = details

        kb["policies"] = policies
        print(f"New policy '{policy_key}' added.")

        return kb

    # -------------------------------
    # FAQ INSERT
    # -------------------------------
    def _insert_faq(self, kb, question: str, answer: str):
        """
        Insert a new FAQ entry.
        
        Format:
        - question: The customer question
        - answer: The standard answer
        """
        kb["faqs"].append({
            "q": question,
            "a": answer
        })

        print(f"New FAQ added - Q: {question}")

        return kb
