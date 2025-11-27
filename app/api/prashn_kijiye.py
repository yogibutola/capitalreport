# File: main.py

from fastapi import FastAPI, status, Query
from fastapi.middleware.cors import CORSMiddleware

from app.agents.genaiway.pdfdocument_extraction.document_reader.document_reader import DocumentReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.excel_reader import ExcelReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.pdf_reader import PDFReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.word_reader import WordReader
from app.agents.genaiway.pdfdocument_extraction.orchestrator import Orchestrator
from app.agents.genaiway.pdfdocument_extraction.pdf_agent import PdfAgent
from app.agents.genaiway.pdfdocument_extraction.util.embed_data import EmbedData
from app.agents.genaiway.pdfdocument_extraction.util.text_splitter import TextSplitter

app = FastAPI(title="Query Param Example")

origins = [
    "http://localhost:4200",  # <--- YOUR FRONTEND ORIGIN
    "http://127.0.0.1:4200",
    "http://0.0.0.0:4200"
    # (Optional: Sometimes localhost maps to 127.0.0.1)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allows cookies, authorization headers, etc.
    allow_methods=["*"],  # Allows all HTTP methods (POST, GET, PUT, etc.)
    allow_headers=["*"],  # Allows all headers from the request
)


def get_orchestrator(self) -> Orchestrator:
    """Dependency injector that provides an Orchestrator instance."""
    pdf_agent = PdfAgent()
    pdf_reader = PDFReader()
    word_reader = WordReader()
    excel_reader = ExcelReader()
    document_reader = DocumentReader(pdf_reader, word_reader, excel_reader)

    text_splitter = TextSplitter()
    embed_data = EmbedData()
    return Orchestrator(pdf_agent, document_reader, text_splitter, embed_data)


@app.api_route("/prahn_kijiye/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document(documents: str,
                   query: str = Query("Describe the document",  # Default value if no query parameter is provided
                                      title="Name to Greet",
                                      description="The name to include in the greeting response.")):
    orchestrator = get_orchestrator()
    response: str = orchestrator.ask_question(query, documents)
    return {"answer": f"You answer: {response}"}

@app.api_route("/ask_question/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document(documents: str,
                   query: str = Query("Describe the document",  # Default value if no query parameter is provided
                                      title="Name to Greet",
                                      description="The name to include in the greeting response.")):
    orchestrator = get_orchestrator()
    response: str = orchestrator.prashn_kijiye(query, documents)
    return {"answer": f"You answer: {response}"}