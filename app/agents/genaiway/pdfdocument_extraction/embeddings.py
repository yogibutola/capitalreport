
from dotenv import load_dotenv

load_dotenv()

class Embeddings:
    PROJECT_ID = "butola-ai-project"
    EMBEDDING_MODEL_NAME = "text-embedding-005"
    MODEL_NAME = "gemini-2.0-flash-exp"
    embedding_model = ""

    def __init__(self):
        print("Constructing embedding object")
        self.embedding_model = VertexAIEmbeddings(project=Embeddings.PROJECT_ID, model=Embeddings.EMBEDDING_MODEL_NAME)

    def getEmbedding(self, text):
        """Generates vector embeddings for the given text."""
        return self.embedding_model.embed_query(text)
