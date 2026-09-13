import logging
import os
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, DESCENDING
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBAuditStore:
    """Persistence for the ``audit_log`` collection - one document per recorded
    user action, powering the platform console activity feed and metrics."""

    _indexes_ready = False

    def __init__(self, mongo_uri=None, db_name="pickleball"):
        uri = mongo_uri or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI environment variable must be set")
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_collection(self) -> Collection:
        collection = self.db["audit_log"]
        if not PBAuditStore._indexes_ready:
            try:
                collection.create_index([("ts", DESCENDING)])
                collection.create_index([("actor", 1), ("ts", DESCENDING)])
                collection.create_index([("action", 1), ("ts", DESCENDING)])
                PBAuditStore._indexes_ready = True
            except Exception:  # pragma: no cover - index creation is best-effort
                self.logger.warning("Could not create audit_log indexes", exc_info=True)
        return collection

    def record(self, entry: dict) -> None:
        """Insert one audit entry. Callers treat this as best-effort."""
        self.get_collection().insert_one(dict(entry))

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Most-recent-first slice of the activity feed, with optional filters."""
        q: dict = {}
        if actor:
            q["actor"] = actor.lower()
        if action:
            q["action"] = action
        if since:
            q["ts"] = {"$gte": since}

        limit = max(1, min(limit, 1000))
        docs = list(self.get_collection().find(q).sort("ts", DESCENDING).limit(limit))
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
        return docs

    def metrics(self) -> dict:
        """Aggregate counters for the console header."""
        collection = self.get_collection()
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)

        active_actors = collection.distinct("actor", {"ts": {"$gte": since_24h}})
        return {
            "actions_24h": collection.count_documents({"ts": {"$gte": since_24h}}),
            "active_actors_24h": len([a for a in active_actors if a and a != "anonymous"]),
            "signins_7d": collection.count_documents(
                {"ts": {"$gte": since_7d}, "action": "Signed in"}
            ),
            "errors_24h": collection.count_documents(
                {"ts": {"$gte": since_24h}, "status_code": {"$gte": 400}}
            ),
        }
