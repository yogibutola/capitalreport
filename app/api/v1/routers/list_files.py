from fastapi import status, APIRouter

from app.services.load_files import LoadFiles

router = APIRouter(tags=["ListFiles"])


@router.api_route("/list_files/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document(file_type: str) -> list[str]:
    load_files = LoadFiles()
    files: list[str] = load_files.find_files(file_type)
    return files
