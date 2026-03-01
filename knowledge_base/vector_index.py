import chromadb
#from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import config.config as config
from sentence_transformers import SentenceTransformer

class VectorIndex:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.PERSIST_DIR)

        self.collection_name = config.COLLECTION_NAME
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
            docs.append(f"Q: {faq['q']} A: {faq['a']}")
            ids.append(f"faq-{i}")
            i += 1

        for service_name, service_info in kb_data.get("services", {}).items():
            docs.append(
                f"Service: {service_name}, Price: {service_info.get('price')}"
            )
            ids.append(f"service-{i}")
            i += 1

        # Add documents
        if docs:
            model = SentenceTransformer(config.TRANSFORMER)
            embeddings = model.encode(docs).tolist()
            self.collection.add(
                ids=ids,
                documents=docs,
                embeddings=embeddings
            )


        print("Vector DB rebuilt successfully.")
