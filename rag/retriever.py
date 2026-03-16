import os
import logging
from pathlib import Path
from rag.vector_store import EmailVectorStore
from knowledge_base.ingestion import load_email_kb
from knowledge_base.kb_store import KBStore
import config.config as cfg

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    def __init__(self):
        self.store = EmailVectorStore()
        self.kb_store = KBStore()
        self._load_latest_kb()

    def _load_latest_kb(self):
        """
        Load the most recent KB version from database.
        Query index for RAG.
        """
        try:
            # First try to load from database
            kb_data = self.kb_store.get_current_kb()
            logger.info("Loaded KB from database")
        except Exception as e:
            logger.warning(f"Failed to load KB from database: {e}. Falling back to file.")
            # Fallback to file if database not available
            print(f"Loading latest KB version: {cfg.INITIAL_KB_JSON_PATH}")
            kb_data = load_email_kb(cfg.INITIAL_KB_JSON_PATH)
            items = self.store.add_documents(items)
            return
            
        # Process KB data for vector store
        items = self._process_kb_for_vectorstore(kb_data)
        self.store.add_documents(items)

    def _process_kb_for_vectorstore(self, kb_data: dict):
        """
        Convert KB data structure to documents for vector storage.
        """
        items = []
        
        # Extract services
        services = kb_data.get("services", {})
        for service_key, service_info in services.items():
            desc = service_info.get("description", "")
            price = service_info.get("price", "")
            items.append(f"Service: {service_key} - {desc} Price: {price}")
        
        # Extract policies
        policies = kb_data.get("policies", {})
        for policy_key, policy_text in policies.items():
            items.append(f"Policy: {policy_key} - {policy_text}")
        
        # Extract FAQs
        faqs = kb_data.get("faqs", [])
        for faq in faqs:
            q = faq.get("q", "")
            a = faq.get("a", "")
            items.append(f"FAQ: Q: {q} A: {a}")
        
        logger.debug(f"Converted KB to {len(items)} vector store documents")
        return items

    def retrieve(self, query: str):
        return self.store.query(query)
