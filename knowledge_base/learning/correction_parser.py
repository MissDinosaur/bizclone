import re


class CorrectionParser:
    """
    Automatically parses owner correction text.

    Detects:
    - KB section (pricing / policy / faq)
    - Target service (if applicable)
    - Extracted price value
    """

    def __init__(self, kb_services: dict):
        self.service_keys = list(kb_services.keys())

    def parse(self, correction_text: str):
        text = correction_text.lower()

        # -------------------------
        # Detect pricing updates
        # -------------------------
        price_match = re.search(r"€\s?\d+", correction_text)

        if price_match:
            new_price = price_match.group()

            # Try match service name
            for service_key in self.service_keys:
                service_name = service_key.replace("_", " ")

                if service_name in text:
                    return {
                        "kb_field": "pricing",
                        "service_key": service_key,
                        "new_value": f"{new_price} per hour (updated)"
                    }

            # Emergency fallback
            if "emergency" in text:
                return {
                    "kb_field": "pricing",
                    "service_key": "emergency_plumbing",
                    "new_value": f"{new_price} per hour (emergency rate)"
                }

            return {
                "kb_field": "pricing",
                "service_key": None,
                "new_value": f"{new_price} (general price update)"
            }

        # -------------------------
        # Detect policy updates
        # -------------------------
        if "cancel" in text or "cancellation" in text:
            return {
                "kb_field": "policy",
                "policy_key": "cancellation",
                "new_value": correction_text
            }

        if "payment" in text:
            return {
                "kb_field": "policy",
                "policy_key": "payment_methods",
                "new_value": correction_text
            }

        if "late" in text:
            return {
                "kb_field": "policy",
                "policy_key": "late_arrival",
                "new_value": correction_text
            }

        # -------------------------
        # Default fallback: FAQ update
        # -------------------------
        return {
            "kb_field": "faq",
            "new_value": correction_text
        }
