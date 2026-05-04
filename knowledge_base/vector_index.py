import chromadb
import logging
#from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import config.config as cfg
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class VectorIndex:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=cfg.PERSIST_DIR)

        self.collection_name = cfg.COLLECTION_NAME
        # Create or load collection
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    # -------------------------------
    # Rebuild Vector Index Safely
    # -------------------------------
    def rebuild_index(self, kb_data: dict):
        """
        Fully rebuild vector DB after KB updates.
        """

        print("Rebuilding vector index...")

        # Clear old documents
        try:
            self.collection.delete(where={})
            print("Old documents cleared.")
        except Exception:
            print("No previous documents found.")

        # Recreate collection
        # self.collection = self.client.get_or_create_collection(name=self.collection_name)

        # Re-insert KB chunks
        docs = []
        ids = []

        i = 0
        for faq in kb_data.get("faqs", []):
            # faq is now a dict (SQLAlchemy JSON type returns Python objects)
            if isinstance(faq, dict):
                q_text = faq.get('q', '')
                a_text = faq.get('a', '')
                if q_text or a_text:
                    docs.append(f"Q: {q_text} A: {a_text}")
                    ids.append(f"faq-{i}")
                    i += 1

        for service_name, service_info in kb_data.get("services", {}).items():
            # service_info is now a dict (SQLAlchemy JSON type returns Python objects)
            if isinstance(service_info, dict):
                price = service_info.get('price', '')
                docs.append(f"Service: {service_name}, Price: {price}")
                ids.append(f"service-{i}")
                i += 1

        # Add documents
        if docs:
            model = SentenceTransformer(cfg.TRANSFORMER)
            embeddings = model.encode(docs).tolist()
            self.collection.add(
                ids=ids,
                documents=docs,
                embeddings=embeddings
            )


        print("Vector DB rebuilt successfully.")
