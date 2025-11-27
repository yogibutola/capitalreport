import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class ReadChunkEmbed:
    EMBEDDING_MODEL = "models/text-embedding-004"
    GENERATIVE_MODEL = "gemini-1.5-flash"

    def get_client(self):
        client = genai.Client()
        return client

    def create_embeddings_and_index(self, text: str) -> list:
        """
        Splits the document into paragraphs, generates embeddings for each,
        and stores them in a list for in-memory retrieval.
        """
        EMBEDDING_MODEL = "models/text-embedding-004"
        print("Processing document and generating embeddings...")
        chunks = text.split("\n\n")
        if not chunks:
            print("Document is empty or not properly formatted.")
            return []

        # Get embeddings for all chunks in a single batch request for efficiency.
        try:
            client = self.get_client()
            response = client.models.embed_content(model=EMBEDDING_MODEL, contents=chunks)
            embeddings = response.embeddings
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return []

        # Create an in-memory "database" of chunks and their embeddings.
        return [
            {"text": chunk, "embedding": np.array(embedding)}
            for chunk, embedding in zip(chunks, embeddings)
        ]

    def find_most_relevant_chunk(self, query: str, indexed_chunks: list) -> str:
        """
        Finds the most semantically similar chunk to the user's query.
        """
        EMBEDDING_MODEL = "models/text-embedding-004"
        print("Searching for relevant information...")
        if not indexed_chunks:
            return "No document content available."

        try:
            # Generate embedding for the query.
            client = self.get_client()
            query_embedding_response = client.models.embed_content(model=EMBEDDING_MODEL, contents=query)
            query_embedding = np.array(query_embedding_response.embeddings)

            # Calculate cosine similarity between query and all chunk embeddings.


            similarities = [
                np.dot(query_embedding, indexed_chunk['embedding']) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(indexed_chunk['embedding']))
                for indexed_chunk in indexed_chunks
            ]


            # Find the index of the most similar chunk.
            most_similar_index = np.argmax(similarities)

            # Return the most relevant chunk text.
            return indexed_chunks[most_similar_index]['text']
        except Exception as e:
            return f"Error during retrieval: {e}"

    def get_answer_from_context(self, query: str, context: str) -> str:
        """
        Uses the Gemini model to answer the query based on the provided context.
        """
        GENERATIVE_MODEL = "gemini-1.5-flash"
        prompt = f"""
        You are an expert Q&A assistant. Your task is to answer the user's question
        using only the provided context. If the information is not present in the context,
        state that you cannot answer based on the provided information.
    
        Context:
        {context}
    
        Question: {query}
        Answer:
        """

        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.0-flash-001',
            config=types.GenerateContentConfig(
                temperature=0,
            ),
            contents=prompt
        )
        return response.text

        # try:
        #     model = ggenai.GenerativeModel(GENERATIVE_MODEL)
        #     response = model.generate_content(prompt)
        #     return response.text
        # except Exception as e:
        #     return f"Error generating a response from the model: {e}"


def main():
    print("--- Document Q&A System ---")
    # Sample document content. In a real application, you would load this from a file.
    DOCUMENT = """
    The Amazon rainforest is the largest tropical rainforest in the world, covering over 5.5 million square kilometers. It spans nine countries, with the majority of the forest located in Brazil. The rainforest is known for its immense biodiversity, housing millions of species of plants, animals, and insects.

    One of the most critical aspects of the Amazon is its role in the global climate. It produces a significant portion of the world's oxygen and is often referred to as the "Lungs of the Planet." However, deforestation poses a major threat to this vital ecosystem. Logging, cattle ranching, and agricultural expansion are the primary drivers of forest loss.

    Indigenous communities have lived in the Amazon for thousands of years and play a crucial role in its conservation. Their traditional knowledge and sustainable practices are essential for preserving the rainforest's delicate balance. Efforts to protect the Amazon often involve empowering these communities and recognizing their land rights.

    Another interesting fact is the vast network of rivers that crisscross the rainforest, including the mighty Amazon River itself. These rivers are a lifeline for countless species and a major mode of transportation for local people. The Amazon River is the second-longest river in the world, surpassed only by the Nile.
    """
    rce = ReadChunkEmbed()
    # 1. Process the document and create the in-memory index
    indexed_data = rce.create_embeddings_and_index(DOCUMENT)

    if not indexed_data:
        print("Failed to process document. Exiting.")
        return

    # 2. Start a Q&A loop
    while True:
        print("\n---")
        user_query = input("Ask a question about the document (or type 'exit' to quit): ")
        if user_query.lower() == 'exit':
            break

        # 3. Retrieve the most relevant chunk of text
        retrieved_context = rce.find_most_relevant_chunk(user_query, indexed_data)
        print("\n--- Retrieved Context ---")
        print(retrieved_context)

        # 4. Generate an answer using the LLM and the retrieved context
        answer = rce.get_answer_from_context(user_query, retrieved_context)
        print("\n--- Answer ---")
        print(answer)


if __name__ == "__main__":
    main()
