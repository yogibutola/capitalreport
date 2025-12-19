import logging
from typing import Annotated
from typing import List

from fastapi import File, UploadFile, HTTPException, Depends, status, APIRouter

from app.agents.vertex.prashn_uttar_agent import PrashnUttarAgent
from app.services.data_extractor import DataExtractor
from app.services.embed_data import EmbedData
from app.services.orchestrator import Orchestrator
from app.services.text_splitter import TextSplitter
from app.store.gcp_file_store import GCPStore
from app.store.mongo_db_store import MongoDBStore

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["UploadDocuments"])


def get_orchestrator() -> Orchestrator:
    """Dependency injector that provides an Orchestrator instance."""
    prashn_uttar_agent = PrashnUttarAgent()
    data_extractor = DataExtractor()
    text_splitter = TextSplitter()
    embed_data = EmbedData()
    mongodb_store = MongoDBStore()
    return Orchestrator(prashn_uttar_agent, data_extractor, text_splitter, embed_data, mongodb_store)


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
        except BulkWriteError as bwe:
            logger.error(f"Bulk write error occurred: {bwe}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="There was a problem while saving the file. Please try again.",
            ) from None
        except DuplicateKeyError as dke:
            logger.error(f"Duplicate key error occurred: {dke}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This file is already uploaded. Please choose a different file.",
            ) from None
        except Exception as e:
            logger.error(f"Error during file save: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save the file.",
            ) from None
        finally:
            await file.close()

    return {"message": "Files uploaded successfully", "files": saved_files}
