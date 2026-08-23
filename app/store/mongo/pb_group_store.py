from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId
import uuid
import logging
import os
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBGroupStore:
    """MongoDB store for player groups, events, and discussions."""

    def __init__(self, mongo_uri=None, db_name: str = "pickleball"):
        uri = mongo_uri or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI environment variable must be set")
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def _groups_col(self):
        return self.db["groups"]

    # ─────────────────────────────────────────────
    # Group CRUD
    # ─────────────────────────────────────────────

    def create_group(self, name: str, description: str | None, creator_email: str) -> dict:
        """Create a new group owned by creator_email."""
        group = {
            "group_id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "creator_email": creator_email.lower(),
            "members": [creator_email.lower()],
            "events": [],
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self._groups_col().insert_one(group)
        group["_id"] = str(group["_id"])
        self.logger.info(f"Created group '{name}' by {creator_email}")
        return group

    def get_groups_for_player(self, email: str) -> list[dict]:
        """Return all groups where the player is a member."""
        email = email.lower()
        docs = list(self._groups_col().find({"members": email}))
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

    def get_group_by_id(self, group_id: str) -> dict | None:
        """Return a single group document."""
        doc = self._groups_col().find_one({"group_id": group_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # ─────────────────────────────────────────────
    # Members
    # ─────────────────────────────────────────────

    def add_member(self, group_id: str, email: str) -> bool:
        """Add a player to the group. Returns True if the document was found."""
        result = self._groups_col().update_one(
            {"group_id": group_id},
            {"$addToSet": {"members": email.lower()}}
        )
        return result.matched_count > 0

    # ─────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────

    def add_event(self, group_id: str, title: str, date: str, notes: str | None,
                  time: str | None = None, place: str | None = None) -> dict | None:
        """Add a new event to the group. Returns the new event document."""
        event = {
            "event_id": str(uuid.uuid4()),
            "title": title,
            "date": date,
            "time": time,
            "place": place,
            "notes": notes,
            "votes": [],
            "messages": []
        }
        result = self._groups_col().update_one(
            {"group_id": group_id},
            {"$push": {"events": event}}
        )
        if result.matched_count == 0:
            return None
        self.logger.info(f"Added event '{title}' to group {group_id}")
        return event

    # ─────────────────────────────────────────────
    # Event Votes
    # ─────────────────────────────────────────────

    def set_event_vote(self, group_id: str, event_id: str, voter_email: str,
                       voter_name: str, vote: str) -> dict | None:
        """Cast or change a player's vote on an event (one vote per player)."""
        vote_doc = {
            "voter_email": voter_email.lower(),
            "voter_name": voter_name,
            "vote": vote,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        match = {"group_id": group_id, "events.event_id": event_id}
        # Remove any previous vote by this player, then record the new one.
        result = self._groups_col().update_one(
            match,
            {"$pull": {"events.$.votes": {"voter_email": voter_email.lower()}}}
        )
        if result.matched_count == 0:
            return None
        self._groups_col().update_one(
            match,
            {"$push": {"events.$.votes": vote_doc}}
        )
        return vote_doc

    # ─────────────────────────────────────────────
    # Discussion Messages
    # ─────────────────────────────────────────────

    def add_group_message(self, group_id: str, author_email: str, author_name: str, content: str) -> dict | None:
        """Add a message to the group-level discussion."""
        message = {
            "message_id": str(uuid.uuid4()),
            "author_email": author_email.lower(),
            "author_name": author_name,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        result = self._groups_col().update_one(
            {"group_id": group_id},
            {"$push": {"messages": message}}
        )
        if result.matched_count == 0:
            return None
        return message

    def add_event_message(self, group_id: str, event_id: str, author_email: str, author_name: str, content: str) -> dict | None:
        """Add a message to a specific event's discussion thread."""
        message = {
            "message_id": str(uuid.uuid4()),
            "author_email": author_email.lower(),
            "author_name": author_name,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        result = self._groups_col().update_one(
            {"group_id": group_id, "events.event_id": event_id},
            {"$push": {"events.$.messages": message}}
        )
        if result.matched_count == 0:
            return None
        return message
