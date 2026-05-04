from pydantic import BaseModel
from typing import Literal, Optional


class FeedbackEntry(BaseModel):
    """
    Owner feedback entry for updating or inserting KB knowledge.
    
    For SERVICE: service_name, service_description, service_price are used
    For POLICY/FAQ: customer_question, owner_correction are used
    """

    # Generic fields (used for policy and faq)
    customer_question: Optional[str] = None
    owner_correction: Optional[str] = None
    policy_name: Optional[str] = None
    # Service-specific fields (used when kb_field="service")
    service_name: Optional[str] = None
    service_description: Optional[str] = None
    service_price: Optional[str] = None
    
    kb_field: Literal["service", "policy", "faq"]
    operation: Literal["update", "insert"]
  
    @classmethod
    def get_kb_fields(cls):
        return cls.model_fields["kb_field"].annotation.__args__

