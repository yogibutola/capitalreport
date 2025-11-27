import json
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pymongo.synchronous.collection import Collection

from app.agents.genaiway.pdfdocument_extraction.embedding_function import EmbeddData
from app.agents.genaiway.pdfdocument_extraction.investment import Investment
from app.store.mongo_db_store import MongoDBStore

# from embedding_function import EmbeddData
# from investment import Investment

load_dotenv()
GENERATION_MODEL = "gemini-2.5-flash"


class PdfAgent:

    def find_values(self, text: str):
        client = genai.Client()
        # instructions = "You are stock analyst agent, who understands the investment report for an individual account"
        instructions = """
            Format the json response properly so that it can be easily understandable.
        """
        query = """
                Read the document and list the holdings with the following information:
                  Schema = list of objects with fields:
                    - stock_name (string)
                    - quantity (number)
                    - gain_loss (number, float, in USD — no $, no commas, 0 if not applicable))
                """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                temperature=0,
                # tools=[grounding_tool],
                system_instruction=instructions,
                response_schema=list[Investment]
            ),
            contents=[text, query]
        )

        clean_text = re.sub(r"^```json|```$", "", response.text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean_text)
        my_investments = [Investment(**item) for item in data]

        # my_investments: list[Investment] = response.parsed
        return my_investments

    def get_answer(self, embedding_function: EmbeddData, query: str, k: int = 5) -> str:
        """
        Retrieves relevant documents and uses Gemini to generate a refined answer.
        """
        # 1. Retrieval: Find the top 'k' most relevant chunks
        results = embedding_function.collection.query(
            query_texts=[query],
            n_results=k,
            include=['documents', 'metadatas']
        )

        # Check if results are empty
        if not results['documents'] or not results['documents'][0]:
            return "Could not find any relevant information in the document."

        # Format the retrieved context for the prompt
        context = "\n---\n".join(results['documents'][0])

        # 2. Augmented Generation: Craft the RAG prompt
        prompt = f"""
        You are an expert Q&A assistant for the provided document.
        Answer the user's question based *only* on the provided context.
        If the answer is not found in the context, state clearly that you 
        cannot answer based on the provided document.

        ---
        CONTEXT:
        {context}
        ---

        USER QUESTION: {query}
        """

        # 3. Call the Gemini API
        print("Generating answer with Gemini...")
        client = genai.Client()
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt

            # config=types.GenerateContentConfig(
            #     temperature=0,
            #     # tools=[grounding_tool],
            #     system_instruction=instructions,
            #     response_schema=list[Investment]
            # ),
        )

        return response.text

    def get_answer_for_ui_client(self, collection, query: str, k: int = 5) -> str:
        """
        Retrieves relevant documents and uses Gemini to generate a refined answer.
        """
        # 1. Retrieval: Find the top 'k' most relevant chunks
        results = collection.query(
            query_texts=[query],
            n_results=k,
            include=['documents', 'metadatas']
        )

        # Check if results are empty
        if not results['documents'] or not results['documents'][0]:
            return "Could not find any relevant information in the document."

        # Format the retrieved context for the prompt
        context = "\n---\n".join(results['documents'][0])

        # 2. Augmented Generation: Craft the RAG prompt
        prompt = f"""
        You are an expert Q&A assistant for the provided document.
        Answer the user's question based *only* on the provided context.
        If the answer is not found in the context, state clearly that you 
        cannot answer based on the provided document.

        ---
        CONTEXT:
        {context}
        ---

        USER QUESTION: {query}
        """

        # 3. Call the Gemini API
        print("Generating answer with Gemini...")
        client = genai.Client()
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt

            # config=types.GenerateContentConfig(
            #     temperature=0,
            #     # tools=[grounding_tool],
            #     system_instruction=instructions,
            #     response_schema=list[Investment]
            # ),
        )

        return response.text

    def ask_question(self, query: str, embedding_model, collection, k: int = 5):
        """
        Retrieves relevant documents and uses Gemini to generate a refined answer.
        """
        print(f"Config: {collection.configuration_json}")
        # 1. Retrieval: Find the top 'k' most relevant chunks

        query_embedding = embedding_model.get_embeddings([query])[0].values
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=['documents', 'metadatas']
        )

        # Check if results are empty
        if not results['documents'] or not results['documents'][0]:
            return "Could not find any relevant information in the document."

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]

        # Combine document and metadata info
        context_blocks = []
        for doc, meta in zip(documents, metadatas):
            page = meta.get("page")
            filename = meta.get("filename")
            context_blocks.append(f"Filename: {filename} = {page}\n{doc}")

        # Format the retrieved context for the prompt
        context = "\n---\n".join(context_blocks)
        # context = "\n---\n".join(results['documents'][0])

        # 2. Augmented Generation: Craft the RAG prompt
        prompt = f"""
        You are an expert Q&A assistant for the provided document.
        Answer the user's question based *only* on the provided context.
        If the answer is not found in the context, state clearly that you 
        cannot answer based on the provided document.
        
        Also provide the source information at the end, like the filename and page number.

        ---
        CONTEXT:
        {context}
        ---

        USER QUESTION: {query}
        """

        # 3. Call the Gemini API
        print("Generating answer with Gemini...")
        client = genai.Client()
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt

            # config=types.GenerateContentConfig(
            #     temperature=0,
            #     # tools=[grounding_tool],
            #     system_instruction=instructions,
            #     response_schema=list[Investment]
            # ),
        )

        return response.text

    def prashn_kijiye(self, query: str, embedding_model, collection: Collection, documents: list[str], k: int = 5):
        """
        Retrieves relevant documents and uses Gemini to generate a refined answer.
        """
        # print(f"Config: {collection.configuration_json}")
        # 1. Retrieval: Find the top 'k' most relevant chunks

        query_embedding = embedding_model.get_embeddings([query])[0].values
        combined = {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "distances": []
        }

        print(collection.name, collection.count_documents({}))
        mongodb_store = MongoDBStore()
        results = mongodb_store.find(collection, query_embedding, documents)
        found_texts = []
        found_metadatas = []

        for result in results:
            # Extract the document field
            found_texts.append(result.get("text", ""))
            found_metadatas.append(result.get("metadata", {}))

        combined["documents"].extend(found_texts)
        combined["metadatas"].extend(found_metadatas)
        # The following code works for Chroma DB
        # results = collection.query(
        #     query_embeddings=[query_embedding],
        #     n_results=k,
        #     include=['documents', 'metadatas']
        # )
        # Check if results are empty
        # if not results['documents'] or not results['documents'][0]:
        #     return "Could not find any relevant information in the document."

        # Each is wrapped in a list: res["documents"][0]
        # combined["documents"].extend(results.get("documents", [[]])[0])
        # combined["metadatas"].extend(results.get("metadatas", [[]])[0])
        # combined["ids"].extend(results.get("ids", [[]])[0])
        # combined["distances"].extend(results.get("distances", [[]])[0])

        documents = combined['documents']
        metadatas = combined['metadatas']

        # Combine document and metadata info
        context_blocks = []
        for doc, meta in zip(documents, metadatas):
            page = meta.get("page")
            filename = meta.get("filename")
            context_blocks.append(f"Filename: {filename} = {page}\n{doc}")

        # Format the retrieved context for the prompt
        context = "\n---\n".join(context_blocks)
        # context = "\n---\n".join(results['documents'][0])

        # 2. Augmented Generation: Craft the RAG prompt
        prompt = f"""
        You are an expert Q&A assistant for the provided document.
        Answer the user's question based *only* on the provided context.
        If the answer is not found in the context, state clearly that you 
        cannot answer based on the provided document.

        Also provide the source information at the end, like the filename and page number.

        ---
        CONTEXT:
        {context}
        ---

        USER QUESTION: {query}
        """

        # 3. Call the Gemini API
        print("Generating answer with Gemini...")
        client = genai.Client()
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt

            # config=types.GenerateContentConfig(
            #     temperature=0,
            #     # tools=[grounding_tool],
            #     system_instruction=instructions,
            #     response_schema=list[Investment]
            # ),
        )

        return response.text
