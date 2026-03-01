import re
from knowledge_base.kb_manager import KnowledgeBaseManager


class KnowledgeBaseUpdater:
    """
    Applies owner corrections into structured KB fields:
    - services pricing
    - policies
    - FAQs
    """

    def __init__(self):
        self.kb_manager = KnowledgeBaseManager()

    # -------------------------------
    # MAIN ENTRY POINT
    # -------------------------------
    def apply_update(self, feedback_entry: dict):
        """
        Apply correction into the correct KB section.
        """
        kb_field = feedback_entry["kb_field"]
        customer_question = feedback_entry["customer_question"]
        owner_correction = feedback_entry["owner_correction"]
        correction_text = f"{customer_question} - {owner_correction}".strip()
        print(f"owner correction is: {owner_correction}.")
        print(f"kb_field is: {kb_field}.")

        kb = self.kb_manager.load_kb()

        if kb_field == "pricing":
            kb = self._update_service_price(kb, correction_text)

        elif kb_field == "policy":
            kb = self._update_policy(kb, correction_text)

        elif kb_field == "faq":
            kb = self._update_faq(kb, correction_text)

        else:
            print("Unknown kb_field, fallback to FAQ append.")
            kb = self._update_faq(kb, correction_text)

        # Save updated KB (with version backup)
        self.kb_manager.update_kb(kb)

        return kb

    # -------------------------------
    # PRICING UPDATE
    # -------------------------------
    def _update_service_price(self, kb, correction_text):
        """
        Update service pricing if correction mentions a known service.
        Example:
        "Emergency plumbing costs €120/hour."
        """

        services = kb.get("services", {})

        # Detect price in text
        price_match = re.search(r"€\s?\d+", correction_text)

        if not price_match:
            print("No price found in correction.")
            return kb

        new_price = price_match.group()

        # Match service keyword
        for service_key in services.keys():

            if service_key.replace("_", " ") in correction_text.lower():
                print(f"Updating price for service: {service_key}")

                services[service_key]["price"] = f"{new_price} per hour (updated)"

                kb["services"] = services
                return kb

        # Special emergency keyword fallback
        if "emergency" in correction_text.lower():
            print("Updating emergency_plumbing price")

            kb["services"]["emergency_plumbing"]["price"] = (
                f"{new_price} per hour (emergency rate)"
            )

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
