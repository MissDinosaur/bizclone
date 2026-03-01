import os
from pathlib import Path
from rag.vector_store import EmailVectorStore
from knowledge_base.ingestion import load_email_kb
import config.config as config


class KnowledgeRetriever:
    def __init__(self):
        self.store = EmailVectorStore()
        self._load_latest_kb()

    def _load_latest_kb(self):
        """
        Load the most recent KB version file dynamically.
        Query index for RAG.
        """

        """
        kb_versions_dir = config.KB_VERSIONS_DIR
        print(f"KB versions folder: {kb_versions_dir}")
        files = sorted([f for f in os.listdir(kb_versions_dir) if f.endswith(".json")])

        if not files:
            raise RuntimeError("No KB version files found!")

        latest_kb_file = files[-1]
        latest_kb_path = os.path.join(kb_versions_dir, latest_kb_file)
        """
        latest_kb_path = config.LATEST_KB_JSON_FILE_PATH
        print(f"Loading latest KB version: {latest_kb_path}")

        items = load_email_kb(latest_kb_path)
        self.store.add_documents(items)

    def retrieve(self, query: str):
        return self.store.query(query)
