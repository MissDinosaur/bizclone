import chromadb
from sentence_transformers import SentenceTransformer
import config.config as config


class EmailVectorStore:
    def __init__(self, persist_dir=config.PERSIST_DIR):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(config.COLLECTION_NAME)
        self.model = SentenceTransformer(config.TRANSFORMER)

    def add_documents(self, items):
        for item in items:
            embedding = self.model.encode(item.content).tolist()

            self.collection.add(
                ids=[item.id],
                documents=[item.content],
                embeddings=[embedding],
                metadatas=[{"category": item.category}]
            )

    def query(self, text, top_k=3):
        embedding = self.model.encode(text).tolist()

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )
        return results["documents"][0]
