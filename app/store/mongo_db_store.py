from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection

import logging

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MongoDBStore:
    def __init__(self, mongo_uri="mongodb://localhost:27017/?directConnection=true", db_name="document_embeddings"):
        uri = "mongodb+srv://yogender_db_user:egyFPoU9emubk13N@cluster0.ggoh6bt.mongodb.net/?appName=Cluster0"
        # self.client = MongoClient(mongo_uri)
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_collection_by_name(self, name: str) -> Collection:
        normalized = name.strip().replace(" ", "_")
        collection_name = f"document_knowledge_base_{normalized}"
        return self.db[collection_name]

    def get_collection(self) -> Collection:
        collection_name = f"document_knowledge_base"
        return self.db[collection_name]

    def store_pdf_embeddings_to_mongo_db(self, filename: str, embeddings: list, texts: list, metadatas: list[dict]):
        self.logger.info("Fetching a collection.")
        collection = self.get_collection()

        docs_to_insert = []
        for i, (text, meta, emb) in enumerate(zip(texts, metadatas, embeddings)):
            doc = {
                "_id": f"{filename}_chunk_{i}",
                "filename": filename,
                "chunk_index": i,
                "text": text,
                "metadata": meta,
                "embedding": emb  # typically a list[float]
            }
            docs_to_insert.append(doc)

        if docs_to_insert:
            # insert_many automatically overwrites duplicates only if ordered=False
            self.logger.info("Inserting documents to the collection.")
            collection.insert_many(docs_to_insert, ordered=False)
            # print(f"Stored {len(docs_to_insert)} chunks in MongoDB collection '{collection.name}'.")
        else:
            self.logger.info("No chunks to store.")

    def find(self, collection: Collection, query_embedding, documents: list[str]):
        query_vector = query_embedding

        # The MongoDB Aggregation Pipeline
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",  # Name of your Search Index in Atlas
                    "path": "embedding",  # Field where your vectors are stored
                    "queryVector": query_vector,
                    "numCandidates": 100,  # How many neighbors to look at (approx)
                    "limit": 5,  # n_results (how many to return)
                    "filter": {
                        "filename": {
                            "$in": documents  # documents = ["file1.pdf", "file2.pdf", ...]
                        }
                    }
                }
            },
            {
                "$project": {  # This replaces include=['documents', 'metadatas']
                    "_id": 0,
                    "text": 1,  # Assuming your text is stored in 'document'
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"}  # Optional: see similarity score
                }
            }
        ]

        # Run the query
        results = list(collection.aggregate(pipeline))
        return results
