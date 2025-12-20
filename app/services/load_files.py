import logging
from app.store.mongo_db_store import MongoDBStore
from app.store.gcp_file_store import GCPStore

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class LoadFiles:
    def __init__(self, gcp_store: GCPStore, mongo_store: MongoDBStore):
        self.gcp_store = gcp_store
        self.mongo_store = mongo_store
        self.logger = logging.getLogger(__name__)

    def find_files(self, file_type: str) -> list[str]:
        list_files: list[str] = self.gcp_store.list_files(file_type)
        return list_files

    def delete_file(self, filename: str):
        self.gcp_store.delete_file(filename)
        self.mongo_store.delete_document(filename)

    def delete_files(self, filenames: list[str]):
        """Deletes multiple files from GCP and MongoDB."""
        for filename in filenames:
            self.delete_file(filename)


