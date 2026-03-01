import json
from knowledge_base.schema import KnowledgeItem


def load_email_kb(path: str):
    """
    Load structured business KB JSON and convert it into
    a flat list of KnowledgeItem for RAG embedding.
    """

    with open(path, "r", encoding="utf-8") as f:
        kb = json.load(f)

    items = []

    # ---------------------------
    # 1. Services
    # ---------------------------
    services = kb.get("services", {})
    for service_id, service_data in services.items():
        items.append(
            KnowledgeItem(
                id=f"service_{service_id}",
                category="service",
                title=service_id.replace("_", " ").title(),
                content=(
                    f"{service_data['description']} "
                    f"Price: {service_data['price']}."
                ),
                tags=["service", "pricing"],
                version=1
            )
        )

    # ---------------------------
    # 2. Policies
    # ---------------------------
    policies = kb.get("policies", {})
    for policy_key, policy_text in policies.items():
        items.append(
            KnowledgeItem(
                id=f"policy_{policy_key}",
                category="policy",
                title=policy_key.replace("_", " ").title(),
                content=policy_text,
                tags=["policy"],
                version=1
            )
        )

    # ---------------------------
    # 3. FAQs
    # ---------------------------
    faqs = kb.get("faqs", [])
    for i, faq in enumerate(faqs):
        items.append(
            KnowledgeItem(
                id=f"faq_{i+1:03d}",
                category="faq",
                title=faq["q"],
                content=faq["a"],
                tags=["faq"],
                version=1
            )
        )

    return items
