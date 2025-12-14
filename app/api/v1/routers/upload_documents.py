from typing import Annotated
from typing import List

from fastapi import File, UploadFile, HTTPException, Depends, status, APIRouter

from app.agents.genaiway.pdfdocument_extraction.document_reader.document_reader import DocumentReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.excel_reader import ExcelReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.pdf_reader import PDFReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.word_reader import WordReader
from app.agents.genaiway.pdfdocument_extraction.orchestrator import Orchestrator
from app.agents.genaiway.pdfdocument_extraction.pdf_agent import PdfAgent
from app.agents.genaiway.pdfdocument_extraction.util.embed_data import EmbedData
from app.agents.genaiway.pdfdocument_extraction.util.text_splitter import TextSplitter
from app.store.gcp_file_store import GCPStore

import logging

logging.basicConfig(
    level=logging.INFO, # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["UploadDocuments"])


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


@router.post("/upload-files/")
async def upload_files(orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
                       files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    logger.info("Uploading files.")
    saved_files = []
    gcp_store = GCPStore()
    for file in files:
        try:
            gcs_url: str = gcp_store.upload_stream_to_gcs(file)
            orchestrator.store_the_docs(file, gcs_url)
            logger.info(f"GCP Storage URL: {gcs_url}")
        except Exception as e:
            logger.error(f"Error during file save: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save the file.",
            ) from None
        finally:
            await file.close()

    return {"message": "Files uploaded successfully", "files": saved_files}
