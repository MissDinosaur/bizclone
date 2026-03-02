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
