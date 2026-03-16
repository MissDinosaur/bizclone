import logging
from knowledge_base.learning.feedback_store import FeedbackStore
from knowledge_base.learning.kb_updater import KnowledgeBaseUpdater
from knowledge_base.vector_index import VectorIndex

logger = logging.getLogger(__name__)


class LearningMode:
    """
    Full Learning Mode Workflow (now database-backed):
    - Save feedback to database (linked to KB version)
    - Update KB with change description
    - Store KB version in database
    - Rebuild vector DB
    """

    def __init__(self):
        self.store = FeedbackStore()
        self.updater = KnowledgeBaseUpdater()
        self.vector_index = VectorIndex()

    def process_feedback(self, feedback_entry: dict):
        """
        Main learning loop with database persistence.
        Args:
            feedback_entry: dict with operation, kb_field, customer_question,
                           owner_correction, and optional service details
        Returns: dict with status and version_number
        """
        logger.info(f"Processing feedback: {feedback_entry.get('operation')} on {feedback_entry.get('kb_field')}")

        try:
            # Step 1: Apply KB update/insert and save to database
            if feedback_entry.get("operation") == "update":
                logger.info("Updating knowledge base from database")
                print("Updating knowledge base.")
                updated_kb, version_number = self.updater.apply_update(feedback_entry=feedback_entry)
                
            elif feedback_entry.get("operation") == "insert":
                logger.info("Inserting new entry into knowledge base")
                print("Inserting new entry into knowledge base.")
                updated_kb, version_number = self.updater.apply_insert(feedback_entry=feedback_entry)
            else:
                logger.error(f"Unknown operation: {feedback_entry.get('operation')}")
                return {"status": "error", "message": "Unknown operation type"}
                
            # Step 2: Save feedback to database with version linkage
            self.store.save(feedback_entry, kb_version_id=version_number)
            logger.info(f"Feedback saved and linked to version {version_number}")
            
            # Step 3: Rebuild vector DB so RAG uses new knowledge
            logger.info("Rebuilding vector index")
            print("Rebuilding vector index...")
            self.vector_index.rebuild_index(updated_kb)
            
            logger.info(f"Learning update applied successfully - version {version_number}")
            return {
                "status": "success",
                "message": "Learning update applied successfully",
                "version_number": version_number
            }
            
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Learning update failed: {str(e)}"
            }
