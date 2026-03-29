import chromadb
from sentence_transformers import SentenceTransformer
import config.config as cfg
import logging

logger = logging.getLogger(__name__)


class EmailVectorStore:
    def __init__(self, persist_dir=cfg.PERSIST_DIR):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(cfg.COLLECTION_NAME)
        self.model = SentenceTransformer(cfg.TRANSFORMER)

    def add_documents(self, items):
        for idx, item in enumerate(items):
            # Handle both string and object inputs
            if isinstance(item, str):
                content = item
                doc_id = f"kb_item_{idx}"
                category = "kb"
            else:
                content = item.content
                doc_id = item.id
                category = item.category
            
            embedding = self.model.encode(content).tolist()

            self.collection.add(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[{"category": category}]
            )

    def query(self, text, top_k=3):
        embedding = self.model.encode(text).tolist()

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )
        return results["documents"][0]
