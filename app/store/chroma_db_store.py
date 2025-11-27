import chromadb
from chromadb.config import Settings


class ChromaDBStore:

    def store_pdf_embeddings(self, filename: str, embeddings: list, texts: list, metadatas: list[str:str]):
        collection = self.get_collection(filename)
        for i, (text, meta, emb) in enumerate(zip(texts, metadatas, embeddings)):
            collection.add(
                ids=[f"{filename}_chunk_{i}"],
                embeddings=[emb],
                documents=[text],
                metadatas=[meta]
            )
            print(f"Stored {i} chunks in ChromaDB collection '{collection}'.")

        print(f"Stored all the chunks in ChromaDB collection '{collection}'.")

    def get_collection(self, collection_name: str):
        collection_name = collection_name.strip().replace(' ', '_')
        chroma_client = chromadb.Client(Settings(persist_directory="./chroma_store"))
        COLLECTION_NAME = "pdf_knowledge_base_" + collection_name
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        return collection
