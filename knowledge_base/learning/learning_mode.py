from knowledge_base.learning.feedback_store import FeedbackStore
from knowledge_base.learning.kb_updater import KnowledgeBaseUpdater
from knowledge_base.vector_index import VectorIndex


class LearningMode:
    """
    Full Learning Mode Workflow:
    - Receive owner feedback
    - Store feedback log
    - Update KB
    - Rebuild vector DB
    """

    def __init__(self):
        self.store = FeedbackStore()
        self.updater = KnowledgeBaseUpdater()
        self.vector_index = VectorIndex()

    def process_feedback(self, feedback_entry: dict):
        """
        Main learning loop.
        """

        # Step 1: Save correction log
        self.store.save(feedback_entry)

        # Step 2: Update KB JSON
        updated_kb = self.updater.apply_update(feedback_entry=feedback_entry)

        # Step 3: Rebuild vector DB so RAG uses new knowledge
        self.vector_index.rebuild_index(updated_kb)

        return {"status": "Learning update applied successfully"}
