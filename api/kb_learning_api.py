from fastapi import APIRouter
from knowledge_base.learning.feedback_entry import FeedbackEntry
from knowledge_base.learning.learning_mode import LearningMode


router = APIRouter()
learning_system = LearningMode()


@router.post("/learning/feedback")
def submit_feedback(entry: FeedbackEntry):
    """
    Core Learning Mode API:
    Business owner submits correction feedback.
    """

    result = learning_system.process_feedback(entry.dict())

    return result


"""
Business owner sends feedback:

curl -X POST http://localhost:8000/learning/feedback \
  -H "Content-Type: application/json" \
  -d '{
curl -X POST http://localhost:8000/learning/feedback \
  -H "Content-Type: application/json" \
  -d '{
        "customer_question": "How much is emergency plumbing?",
        "agent_reply": "Emergency plumbing costs €100/hour.",
        "owner_correction": "Emergency plumbing costs €120/hour.",
        "intent": "pricing inquiry",
        "kb_field": "pricing"
      }'
"""