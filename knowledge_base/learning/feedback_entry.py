from pydantic import BaseModel
from typing import Literal


class FeedbackEntry(BaseModel):
    """
    Owner correction feedback.
    We store full feedback context (question, agent reply, correction, intent) 
    to support auditability and future model fine-tuning.

    Example:
    - Question: "How much is emergency plumbing?"
    - Agent Answer: "Emergency plumbing costs €100/hour"
    - Owner Correction: "No, it's €120/hour"
    """

    customer_question: str
    owner_correction: str
    kb_field: Literal["pricing", "policy", "faq"]
    operation: Literal["update", "insert"]
    # agent_reply: str
    #     
    @classmethod
    def get_kb_fields(cls):
        return cls.model_fields["kb_field"].annotation.__args__

