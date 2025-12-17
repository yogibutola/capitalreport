from dotenv import load_dotenv
from google.cloud import aiplatform
from pymongo.synchronous.collection import Collection
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel
)

from app.store.mongo_db_store import MongoDBStore

load_dotenv()
GENERATION_MODEL = "gemini-2.5-flash"

import logging

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PrashnUttarAgent:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def prashn_kijiye(self, query: str, embedding_model, collection: Collection, documents: list[str], k: int = 5):
        """
        Retrieves relevant documents and uses Gemini to generate a refined answer.
        """
        # 1. Retrieval: Find the top 'k' most relevant chunks

        query_embedding = embedding_model.get_embeddings([query])[0].values
        combined = {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "distances": []
        }

        self.logger.info(f"Documents: {documents}")
        mongodb_store = MongoDBStore()
        results = mongodb_store.find(collection, query_embedding, documents)
        found_texts = []
        found_metadatas = []

        for result in results:
            found_texts.append(result.get("text", ""))
            found_metadatas.append(result.get("metadata", {}))

        combined["documents"].extend(found_texts)
        combined["metadatas"].extend(found_metadatas)
        documents = combined['documents']
        metadatas = combined['metadatas']

        # Combine document and metadata info
        context_blocks = []
        for doc, meta in zip(documents, metadatas):
            page = meta.get("page")
            filename = meta.get("filename")
            gcs_url = meta.get("gcs_url")
            context_blocks.append(f"Filename: {filename} = {page}\n{doc}\n{gcs_url}")

        # Format the retrieved context for the prompt
        context = "\n---\n".join(context_blocks)

        # 2. Augmented Generation: Craft the RAG prompt
        prompt = f"""
        You are an expert Q&A assistant for the provided document.
        Answer the user's question based *only* on the provided context.
        If the answer is not found in the context, state clearly that you 
        cannot answer based on the provided document.

        Also provide the source information at the end, like the filename and 
        page number. Display the filename as a hyperlink that points to the 
        file’s gcs_url.

        ---
        CONTEXT:
        {context}
        ---

        USER QUESTION: {query}
        """

        PROJECT_ID = "stable-smithy-270416"
        REGION = "us-central1"
        MODEL_NAME = "gemini-2.5-flash"
        # MODEL_NAME = "gemini-3-pro-preview"

        aiplatform.init(project=PROJECT_ID, location=REGION)
        client = GenerativeModel(MODEL_NAME)
        config = GenerationConfig(
            temperature=0,  # Equivalent to temperature=0
            # system_instruction=INSTRUCTIONS,
            # tools=[GROUNDING_TOOL],         # Equivalent to tools=[grounding_tool]
            # response_mime_type="application/json", # Use this with response_schema
            # response_schema=RESPONSE_SCHEMA,      # Equivalent to response_schema=list[Investment]
        )
        response_text: str = ''
        try:
            response = client.generate_content(
                contents=prompt,
                generation_config=config,
            )
            response_text = response.text

        except Exception as e:
            self.logger.error(f"An error occurred while generating the response: {e}")
            return None

        return response_text
