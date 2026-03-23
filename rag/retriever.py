import os
import logging
from pathlib import Path
from rag.vector_store import EmailVectorStore
from knowledge_base.kb_store import KBStore

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    def __init__(self):
        self.store = EmailVectorStore()
        self.kb_store = KBStore()
        self._load_latest_kb()

    def _load_latest_kb(self):
        """
        Load the active KB version from database.
        KB is initialized at database startup from initial_email_kb.json
        """
        try:
            # Load active KB from database
            kb_data = self.kb_store.get_current_kb()
            
            if not kb_data:
                logger.error("No active KB found in database")
                logger.error("KB should have been initialized at database startup from initial_email_kb.json")
                raise RuntimeError("Knowledge base not initialized. Please check database.")
            
            logger.info("✓ Loaded active KB from database")
            
            # Process KB data for vector store
            items = self._process_kb_for_vectorstore(kb_data)
            
            if not items:
                logger.error("Failed to process KB data")
                raise RuntimeError("Failed to process knowledge base data")
            
            # Add all items to vector store
            self.store.add_documents(items)
            logger.info(f"✓ Added {len(items)} KB items to vector store")
            
        except Exception as e:
            logger.error(f"Failed to load KB from database: {e}", exc_info=True)
            raise RuntimeError(f"Knowledge base initialization failed: {e}")

    def _process_kb_for_vectorstore(self, kb_data: dict):
        """
        Convert KB data structure to documents for vector storage.
        Detail fields are now Python objects (dict/string) from SQLAlchemy JSON type.
        """
        if not kb_data:
            logger.warning("KB data is empty or None, returning empty list")
            return []
        
        items = []
        
        try:
            # Extract services - service_info is dict
            services = kb_data.get("services", {})
            for service_key, service_info in services.items():
                if isinstance(service_info, dict):
                    desc = service_info.get("description", "")
                    price = service_info.get("price", "")
                    items.append(f"Service: {service_key} - {desc} Price: {price}")
            
            # Extract policies - policy_text is string
            policies = kb_data.get("policies", {})
            for policy_key, policy_text in policies.items():
                if isinstance(policy_text, str):
                    items.append(f"Policy: {policy_key} - {policy_text}")
            
            # Extract FAQs - faq is dict
            faqs = kb_data.get("faqs", [])
            for faq in faqs:
                if isinstance(faq, dict):
                    q = faq.get("q", "")
                    a = faq.get("a", "")
                    if q or a:
                        items.append(f"FAQ: Q: {q} A: {a}")
            
            logger.debug(f"Converted KB to {len(items)} vector store documents")
        except Exception as e:
            logger.error(f"Error processing KB data for vector store: {e}")
        
        return items

    def retrieve(self, query: str):
        return self.store.query(query)
