# File: main.py

from fastapi import FastAPI, status, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.agents.genaiway.pdfdocument_extraction.document_reader.document_reader import DocumentReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.excel_reader import ExcelReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.pdf_reader import PDFReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.word_reader import WordReader
from app.agents.genaiway.pdfdocument_extraction.orchestrator import Orchestrator
from app.agents.genaiway.pdfdocument_extraction.pdf_agent import PdfAgent
from app.agents.genaiway.pdfdocument_extraction.util.embed_data import EmbedData
from app.agents.genaiway.pdfdocument_extraction.util.text_splitter import TextSplitter

router = APIRouter(tags=["Prashn"])


def get_orchestrator() -> Orchestrator:
    """Dependency injector that provides an Orchestrator instance."""
    pdf_agent = PdfAgent()
    pdf_reader = PDFReader()
    word_reader = WordReader()
    excel_reader = ExcelReader()
    document_reader = DocumentReader(pdf_reader, word_reader, excel_reader)

    text_splitter = TextSplitter()
    embed_data = EmbedData()
    return Orchestrator(pdf_agent, document_reader, text_splitter, embed_data)


@router.api_route("/prahn_kijiye/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document(documents: str,
                   query: str = Query("Describe the document",  # Default value if no query parameter is provided
                                      title="Name to Greet",
                                      description="The name to include in the greeting response.")):
    orchestrator = get_orchestrator()
    response: str = orchestrator.ask_question(query, documents)
    return {"answer": f"You answer: {response}"}


@router.api_route("/ask_question/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document(documents: str,
                   query: str = Query("Describe the document",  # Default value if no query parameter is provided
                                      title="Name to Greet",
                                      description="The name to include in the greeting response.")):
    orchestrator = get_orchestrator()
    response: str = orchestrator.prashn_kijiye(query, documents)
    return {"answer": f"You answer: {response}"}
