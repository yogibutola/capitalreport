from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.genaiway.pdfdocument_extraction.document_reader.document_reader import DocumentReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.excel_reader import ExcelReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.pdf_reader import PDFReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.word_reader import WordReader
from app.agents.genaiway.pdfdocument_extraction.orchestrator import Orchestrator
from app.agents.genaiway.pdfdocument_extraction.pdf_agent import PdfAgent
from app.agents.genaiway.pdfdocument_extraction.util.embed_data import EmbedData
from app.agents.genaiway.pdfdocument_extraction.util.text_splitter import TextSplitter
from app.api.v1.routers import prashn_kijiye
from app.api.v1.routers import generate_report
from app.api.v1.routers import upload_documents
from app.api.v1.routers import list_files
from app.api.v1.routers.pickleball import pb_league
from app.api.v1.routers.pickleball import pb_player
from app.api.v1.routers.pickleball import pb_authorization

app = FastAPI(title="Query Param Example")

origins = [
    "http://localhost:4200",  # <--- YOUR FRONTEND ORIGIN
    "http://127.0.0.1:4200",
    "http://0.0.0.0:4200"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allows cookies, authorization headers, etc.
    allow_methods=["*"],  # Allows all HTTP methods (POST, GET, PUT, etc.)
    allow_headers=["*"],  # Allows all headers from the request
)

app.include_router(prashn_kijiye.router, prefix="/api/v1")
app.include_router(upload_documents.router, prefix="/api/v1")
app.include_router(list_files.router, prefix="/api/v1")
app.include_router(pb_league.router, prefix="/api/v1")
app.include_router(pb_player.router, prefix="/api/v1")
app.include_router(pb_authorization.router, prefix="/api/v1")
app.include_router(generate_report.router, prefix="/api/v1")


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
