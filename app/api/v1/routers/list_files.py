from fastapi import status, APIRouter

from app.services.load_files import LoadFiles
from app.store.gcp_file_store import GCPStore
from app.store.mongo_db_store import MongoDBStore

router = APIRouter(tags=["ListFiles"])


@router.api_route("/list_files/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document() -> list[str]:
    gcp_store = GCPStore()
    mongo_store = MongoDBStore()
    load_files = LoadFiles(gcp_store, mongo_store)
    file_type: str = 'txt'
    files: list[str] = load_files.find_files(file_type)
    return files


@router.api_route("/delete_file/", methods=["DELETE", "OPTIONS"], status_code=status.HTTP_200_OK)
def delete_file(filename: str):
    gcp_store = GCPStore()
    mongo_store = MongoDBStore()
    load_files = LoadFiles(gcp_store, mongo_store)
    load_files.delete_file(filename)
    return {"message": f"File {filename} deleted successfully"}


@router.api_route("/delete_files/", methods=["POST", "OPTIONS"], status_code=status.HTTP_200_OK)
def delete_files(filenames: list[str]):
    gcp_store = GCPStore()
    mongo_store = MongoDBStore()
    load_files = LoadFiles(gcp_store, mongo_store)
    load_files.delete_files(filenames)
    return {"message": f"Deleted {len(filenames)} files successfully"}
