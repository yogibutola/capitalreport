import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction

EMBEDDING_MODEL = "text-embedding-004"
GENERATION_MODEL = "gemini-2.5-flash"
COLLECTION_NAME = "pdf_document_collection"


# Get API key from environment variable
# try:
#     # API_KEY = os.environ['GEMINI_API_KEY']
#     API_KEY = os.environ['GOOGLE_API_KEY']
#
# except KeyError:
#     print("Error: GEMINI_API_KEY environment variable not set.")
#     exit()


class EmbeddData:

    def __init__(self, collection_name: str):
        """Initializes the RAG assistant with the PDF path."""
        # self.pdf_path = pdf_path
        self.chroma_client = chromadb.Client()
        # Initialize the embedding function using the GenAI SDK

        self.gemini_ef = GoogleGenerativeAiEmbeddingFunction(
            api_key="AIzaSyBmAhm92nCmqKSevcSeQJE5",
            model_name=EMBEDDING_MODEL
        )
        # Create or get the ChromaDB collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.gemini_ef
        )
        print(f"Assistant initialized with PDF: {collection_name}")

    def index_document(self, chunks: list[dict]):
        """Processes the PDF, splits it, and stores embeddings in ChromaDB."""
        print("Started Indexing....")
        # Add all chunks to the ChromaDB collection
        self.collection.add(
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
            ids=[c["id"] for c in chunks]
        )
        print("Document indexing complete. Embeddings stored in ChromaDB.")

    def clear_index(self, collection_name: str):
        """Utility to clear the ChromaDB collection."""
        self.chroma_client.delete_collection(name=collection_name)
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.gemini_ef
        )
        print("Index cleared and ready for new document.")

    def get_collection(self, collection_name: str):
        collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.gemini_ef
        )
        return collection
