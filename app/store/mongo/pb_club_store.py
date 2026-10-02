import logging
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, ReturnDocument
from pymongo.collection import Collection

from app.store.mongo.client import PICKLEBALL_DB, get_client


def _oid(value) -> ObjectId | None:
    """ObjectId for ``value``, or None when it isn't a valid id (reads as "not found")."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class PBClubStore:
    """Persistence for ``clubs`` (one per owner) and their ``venues``."""

    _indexes_ready = False

    def __init__(self, mongo_uri=None, db_name=PICKLEBALL_DB):
        self.client = get_client(mongo_uri)
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def clubs(self) -> Collection:
        collection = self.db["clubs"]
        if not PBClubStore._indexes_ready:
            try:
                collection.create_index([("owner_player_id", ASCENDING)], unique=True, name="owner_unique")
                collection.create_index([("slug", ASCENDING)], unique=True, name="slug_unique")
                self.db["venues"].create_index([("club_id", ASCENDING)], name="club")
                PBClubStore._indexes_ready = True
            except Exception:  # pragma: no cover - index creation is best-effort
                self.logger.warning("Could not create clubs/venues indexes", exc_info=True)
        return collection

    def venues(self) -> Collection:
        self.clubs()  # make sure indexes exist
        return self.db["venues"]

    # ---- clubs -------------------------------------------------------------

    def insert_club(self, doc: dict) -> dict:
        """Insert a club; raises ``DuplicateKeyError`` on a taken owner or slug."""
        now = datetime.now(timezone.utc)
        doc = {**doc, "created_at": now, "updated_at": now}
        doc["_id"] = self.clubs().insert_one(doc).inserted_id
        return doc

    def get_club(self, club_id) -> dict | None:
        oid = _oid(club_id)
        return self.clubs().find_one({"_id": oid}) if oid else None

    def get_club_by_owner(self, player_id) -> dict | None:
        oid = _oid(player_id)
        return self.clubs().find_one({"owner_player_id": oid}) if oid else None

    def slug_exists(self, slug: str) -> bool:
        return self.clubs().count_documents({"slug": slug}, limit=1) > 0

    def list_clubs(self) -> list[dict]:
        return list(self.clubs().find().sort("name", ASCENDING))

    def count_clubs(self) -> int:
        return self.clubs().count_documents({})

    def update_club(self, club_id, fields: dict) -> dict | None:
        oid = _oid(club_id)
        if not oid:
            return None
        return self.clubs().find_one_and_update(
            {"_id": oid},
            {"$set": {**fields, "updated_at": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )

    def delete_club(self, club_id) -> bool:
        """Delete a club and its venues. Its leagues/tournaments are left orphaned."""
        oid = _oid(club_id)
        if not oid:
            return False
        deleted = self.clubs().delete_one({"_id": oid}).deleted_count > 0
        if deleted:
            self.venues().delete_many({"club_id": oid})
        return deleted

    # ---- venues ------------------------------------------------------------

    def insert_venue(self, club_id, doc: dict) -> dict:
        now = datetime.now(timezone.utc)
        doc = {**doc, "club_id": _oid(club_id), "created_at": now, "updated_at": now}
        doc["_id"] = self.venues().insert_one(doc).inserted_id
        return doc

    def list_venues(self, club_id) -> list[dict]:
        oid = _oid(club_id)
        return list(self.venues().find({"club_id": oid}).sort("name", ASCENDING)) if oid else []

    def update_venue(self, club_id, venue_id, fields: dict) -> dict | None:
        club_oid, venue_oid = _oid(club_id), _oid(venue_id)
        if not (club_oid and venue_oid):
            return None
        # Scoped by club_id so one club can never edit another's venue.
        return self.venues().find_one_and_update(
            {"_id": venue_oid, "club_id": club_oid},
            {"$set": {**fields, "updated_at": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )

    def delete_venue(self, club_id, venue_id) -> bool:
        club_oid, venue_oid = _oid(club_id), _oid(venue_id)
        if not (club_oid and venue_oid):
            return False
        return self.venues().delete_one({"_id": venue_oid, "club_id": club_oid}).deleted_count > 0
