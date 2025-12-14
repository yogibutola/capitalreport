import vertexai
from vertexai.language_models import TextEmbeddingModel

import logging

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class EmbedData:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_embedding_model(self):
        self.logger.info("Initializing embedding model.")
        vertexai.init(project="stable-smithy-270416", location="us-central1")
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        self.logger.info(f"Initialized embedding model: {model}")
        return model

    def embed_texts(self, texts: list):
        self.logger.info("Embedding text.")
        model = self.get_embedding_model()
        embeddings = model.get_embeddings(texts)
        vectors = [e.values for e in embeddings]
        self.logger.info("Embedding complete.")
        return vectors

    #
    # def store_pdf_embeddings(self, filename: str, embeddings: list, texts: list, metadatas: list[str:str]):
    #     collection = self.get_collection(filename)
    #     for i, (text, meta, emb) in enumerate(zip(texts, metadatas, embeddings)):
    #         collection.add(
    #             ids=[f"{filename}_chunk_{i}"],
    #             embeddings=[emb],
    #             documents=[text],
    #             metadatas=[meta]
    #         )
    #         print(f"Stored {i} chunks in ChromaDB collection '{collection}'.")
    #
    #     print(f"Stored all the chunks in ChromaDB collection '{collection}'.")
    #
    # def get_collection(self, collection_name: str):
    #     collection_name = collection_name.strip().replace(' ', '_')
    #     chroma_client = chromadb.Client(Settings(persist_directory="./chroma_store"))
    #     COLLECTION_NAME = "pdf_knowledge_base_" + collection_name
    #     collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    #     return collection

    def clear_index(self, collection_name: str):
        """Utility to clear the ChromaDB collection."""
        self.chroma_client.delete_collection(name=collection_name)
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.gemini_ef
        )
        self.logger.info("Index cleared and ready for new document.")
