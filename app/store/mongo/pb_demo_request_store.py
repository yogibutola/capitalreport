import logging
import os

from pymongo import DESCENDING
from pymongo.synchronous.collection import Collection
from app.store.mongo.client import get_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBDemoRequestStore:
    """Persistence for the ``demo_requests`` collection - one document per
    "Book a demo" form submission from the public landing site."""

    _indexes_ready = False

    def __init__(self, mongo_uri=None, db_name="pickleball"):
        self.client = get_client(mongo_uri)
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_collection(self) -> Collection:
        collection = self.db["demo_requests"]
        if not PBDemoRequestStore._indexes_ready:
            try:
                collection.create_index([("created_at", DESCENDING)])
                collection.create_index([("email", 1), ("created_at", DESCENDING)])
                PBDemoRequestStore._indexes_ready = True
            except Exception:  # pragma: no cover - index creation is best-effort
                self.logger.warning("Could not create demo_requests indexes", exc_info=True)
        return collection

    def insert(self, doc: dict) -> str:
        """Insert one demo request and return its id as a string."""
        result = self.get_collection().insert_one(dict(doc))
        return str(result.inserted_id)

    def list_recent(self, limit: int = 200) -> list[dict]:
        """Most-recent-first slice of demo requests (platform console use)."""
        limit = max(1, min(limit, 1000))
        docs = list(self.get_collection().find({}).sort("created_at", DESCENDING).limit(limit))
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
        return docs
