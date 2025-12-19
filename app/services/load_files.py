import logging

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class LoadFiles:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def find_files(self, file_type: str) -> list[str]:
        gcp_store = GCPStore()
        list_files: list[str] = gcp_store.list_files(file_type)
        return list_files

