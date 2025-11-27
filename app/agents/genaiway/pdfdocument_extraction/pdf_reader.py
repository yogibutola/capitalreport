# file: pdf_extractor.py

import pdfplumber
from dotenv import load_dotenv
from google import genai
from google.cloud import aiplatform
import textwrap
from pathlib import Path
from pypdf import PdfReader
import chromadb
from chromadb.config import Settings
import vertexai
from vertexai.language_models import TextEmbeddingModel
from chromadb.utils import embedding_functions

load_dotenv()

GENERATION_MODEL = "gemini-2.5-flash"


def extract_text_from_pdf(pdf_path: str, output_txt: str = None) -> str:
    """
    Extracts text from a PDF file and optionally saves it to a text file.

    Args:
        pdf_path (str): Path to the PDF file.
        output_txt (str, optional): Path to save extracted text. Defaults to None.

    Returns:
        str: Extracted text from the PDF.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    extracted_text = []

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            extracted_text.append(f"\n--- Page {page_num} ---\n{text}")

    final_text = "\n".join(extracted_text)

    if output_txt:
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(final_text)

    return final_text


def read_text_from_pdf(pdf_path: str) -> list[str]:
    """Extracts text from the PDF, page by page."""
    print("Extracting text from PDF...")
    reader = PdfReader(pdf_path)
    raw_text = [page.extract_text() for page in reader.pages if page.extract_text()]
    if not raw_text:
        raise ValueError("PDF extraction resulted in no text. Document might be image-based or empty.")

    return raw_text


def split_text_into_chunks(pages: list[str], chunk_size: int = 2000) -> list[str]:
    """Splits the raw text pages into smaller, indexed chunks."""
    chunks = []
    doc_id_counter = 0
    for i, page_text in enumerate(pages):
        # Split the text by a reasonable separator (e.g., double newline)
        for part in page_text.split('\n\n'):
            # Wrap each part to the desired chunk_size if it's too long
            if part.strip():
                # textwrap.wrap handles splitting long strings without cutting words mid-sentence as aggressively
                for chunk_text in textwrap.wrap(part, width=chunk_size, replace_whitespace=False):
                    if chunk_text.strip():
                        chunks.append(chunk_text.strip())
                        # chunks.append({
                        #     "id": f"doc-{doc_id_counter}",
                        #     "text": chunk_text.strip(),
                        #     "metadata": {"page": i + 1}
                        # })
                        doc_id_counter += 1
    print(f"Total chunks created: {len(chunks)}")
    return chunks


def _embed_texts(texts: list) -> list:
    client = genai.Client()
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=texts
    )
    embeddings = [r.values for r in response.embeddings]
    return embeddings


def get_embedding_model():
    vertexai.init(project="stable-smithy-270416", location="us-central1")
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return model


def embed_texts(texts: list):
    # vertexai.init(project="stable-smithy-270416", location="us-central1")
    model = get_embedding_model()
    embeddings = model.get_embeddings(texts)
    vectors = [e.values for e in embeddings]
    print(vectors[0][:5])  # show first 5 embedding values
    return vectors


def store_pdf_embeddings(filename: str, embeddings: list, chunks: list[str]):
    # Add chunks to ChromaDB collection

    collection = get_collection(filename)
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        collection.add(
            ids=[f"{filename}_chunk_{i}"],
            embeddings=[emb],
            documents=[chunk]
        )
        print(f"Stored {i} chunks in ChromaDB collection '{collection}'.")

    print(f"Stored all the chunks in ChromaDB collection '{collection}'.")


def get_collection(collection_name: str):
    chroma_client = chromadb.Client(Settings(persist_directory="./chroma_store"))
    COLLECTION_NAME = "pdf_knowledge_base_" + collection_name
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    return collection


def ask_question(query: str, document_name: str, k: int = 5):
    """
    Retrieves relevant documents and uses Gemini to generate a refined answer.
    """
    print(f"Docuemnt Name: {document_name}")
    collection = get_collection(document_name)

    print(f"Config: {collection.configuration_json}")
    # 1. Retrieval: Find the top 'k' most relevant chunks
    model = get_embedding_model()
    query_embedding = model.get_embeddings([query])[0].values
    results = collection.query(
        query_embeddings=[query_embedding],
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


if __name__ == "__main__":
    # Example usage
    pdf_path = "Statement8312025.pdf"  # replace with your PDF file path
    output_path = "../document_understanding/output.txt"  # optional output file
    text = extract_text_from_pdf(pdf_path, output_path)
    print("PDF extraction completed.")
