import re
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.synchronous.collection import Collection

import logging
import os

from app.vo.pb.league import League
from app.store.mongo.client import get_client

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBPlayerStore:
    def __init__(self, mongo_uri=None, db_name="pickleball"):
        self.client = get_client(mongo_uri)
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_players_collection(self) -> Collection:
        """Get the players collection"""
        collection_name = "players"
        return self.db[collection_name]

    def find_player_by_email(self, email: str):
        """Find a player by email address"""
        collection = self.get_players_collection()
        return collection.find_one({"email": email.lower()})

    def create_player(self, player_data: dict) -> dict:
        """Create a new player in the database"""
        collection = self.get_players_collection()
        # Ensure email is stored in lowercase for consistency
        player_data["email"] = player_data["email"].lower()
        result = collection.insert_one(player_data)
        player_data["_id"] = str(result.inserted_id)
        self.logger.info(f"Successfully created player with email: {player_data['email']}")
        return player_data

    def get_all_players(self) -> list[dict]:
        """Fetch all non-admin players from the database.

        Club (admin) accounts live in the same collection as players, tagged
        ``role="admin"``. They are not players and must never appear in player
        lists / pickers. ``$ne`` also matches legacy docs with no ``role``.
        """
        collection = self.get_players_collection()
        players = list(collection.find({"role": {"$ne": "admin"}}))
        for player in players:
            player["_id"] = str(player["_id"])
        return players

    def find_players(self, first_name: str = None, last_name: str = None,
                     dupr_min: float = None, dupr_max: float = None,
                     exclude_email: str = None) -> list[dict]:
        """Search non-admin players by name substring and DUPR band.

        Every filter is optional; passing none is equivalent to
        ``get_all_players`` with a narrower projection. Names match
        case-insensitively anywhere in the field.

        A ``$gte``/``$lte`` on ``dupr_rating`` also drops documents where the
        field is missing or null, which is exactly the intended behaviour: a
        player with no rating is not "between 3.0 and 4.0".

        Distance is NOT filtered here — Mongo has no coordinates to work with, so
        the caller geocodes each ZIP and filters in Python.

        There is deliberately no index on ``players``: this is a collection scan,
        which at the current scale (hundreds to low thousands of accounts) costs
        single-digit milliseconds. Add one if the roster grows by an order of
        magnitude.
        """
        query: dict = {"role": {"$ne": "admin"}}

        # re.escape so a name containing regex metacharacters is matched literally.
        if first_name:
            query["firstName"] = {"$regex": re.escape(first_name), "$options": "i"}
        if last_name:
            query["lastName"] = {"$regex": re.escape(last_name), "$options": "i"}

        if dupr_min is not None or dupr_max is not None:
            rating: dict = {}
            if dupr_min is not None:
                rating["$gte"] = dupr_min
            if dupr_max is not None:
                rating["$lte"] = dupr_max
            query["dupr_rating"] = rating

        if exclude_email:
            query["email"] = {"$ne": exclude_email.lower()}

        # Explicit projection so the password hash never leaves Mongo.
        projection = {
            "firstName": 1, "lastName": 1, "email": 1, "dupr_rating": 1,
            "role": 1, "city": 1, "state": 1, "zip_code": 1, "paddles": 1,
        }

        collection = self.get_players_collection()
        players = list(collection.find(query, projection))
        for player in players:
            player["_id"] = str(player["_id"])
        return players

    def get_paddles_by_emails(self, emails: list[str]) -> dict[str, list[dict]]:
        """Map lowercased email -> paddles, for views holding stale player copies.

        League and tournament rosters embed a frozen copy of each player taken at
        registration time, so paddles have to be joined in at read time or they'd
        show whatever the player owned the day they signed up. One query for the
        whole roster; players with no paddles are omitted to keep the map small.
        """
        wanted = [e.lower() for e in emails if e]
        if not wanted:
            return {}

        collection = self.get_players_collection()
        docs = collection.find({"email": {"$in": wanted}}, {"email": 1, "paddles": 1})
        return {
            doc["email"].lower(): doc["paddles"]
            for doc in docs
            if doc.get("email") and doc.get("paddles")
        }

    def get_clubs(self) -> list[dict]:
        """Fetch all club (admin) accounts. Mirror of ``get_all_players`` for the
        other side of the ``players`` collection."""
        collection = self.get_players_collection()
        clubs = list(collection.find({"role": "admin"}))
        for club in clubs:
            club["_id"] = str(club["_id"])
        return clubs

    def delete_player_by_email(self, email: str) -> bool:
        """Delete a single account (player or club) by email."""
        collection = self.get_players_collection()
        result = collection.delete_one({"email": email.lower()})
        self.logger.info(
            f"Deleted account {email.lower()}. Deleted count: {result.deleted_count}"
        )
        return result.deleted_count > 0

    def count_by_role(self) -> dict:
        """{'player': n, 'admin': m} counts for the platform metrics header.

        Legacy docs with no ``role`` count as players.
        """
        collection = self.get_players_collection()
        return {
            "admin": collection.count_documents({"role": "admin"}),
            "player": collection.count_documents({"role": {"$ne": "admin"}}),
        }

    def bulk_update_players_league_details(self, emails: list[str], league_data: dict):
        """
        Add a league entry to multiple players at once.
        """
        emails = [e.lower() for e in emails]
        collection = self.get_players_collection()
        league_id = league_data.get("league_id")

        for email in emails:
            # We use a two-step update for each player to avoid duplicates:
            # 1. Update if it exists
            result = collection.update_one(
                {"email": email, "leagues.league_id": league_id},
                {"$set": {"leagues.$": league_data}}
            )
            
            # 2. Push if it doesn't exist
            if result.matched_count == 0:
                collection.update_one(
                    {"email": email},
                    {"$push": {"leagues": league_data}}
                )

    def remove_league_from_player(self, email: str, league_id: str):
        """Remove a league entry from a player's leagues array."""
        collection = self.get_players_collection()
        collection.update_one(
            {"email": email.lower()},
            {"$pull": {"leagues": {"league_id": league_id}}}
        )
        self.logger.info(f"Removed league {league_id} from player {email}")

    def update_player_password(self, email: str, hashed_password: str) -> None:
        """Set a new (already hashed) password for the player with this email."""
        collection = self.get_players_collection()
        collection.update_one(
            {"email": email.lower()},
            {"$set": {"password": hashed_password}}
        )
        self.logger.info(f"Password updated for player {email.lower()}")

    def set_reset_token(self, email: str, token_hash: str, expires_at: datetime) -> None:
        """Store a hashed password-reset token and its expiry for this player."""
        collection = self.get_players_collection()
        collection.update_one(
            {"email": email.lower()},
            {"$set": {"reset_token_hash": token_hash, "reset_token_expires": expires_at}}
        )
        self.logger.info(f"Reset token set for player {email.lower()}")

    def find_player_by_reset_token_hash(self, token_hash: str) -> dict | None:
        """Find a player by their hashed password-reset token."""
        collection = self.get_players_collection()
        return collection.find_one({"reset_token_hash": token_hash})

    def reset_password(self, email: str, hashed_password: str) -> None:
        """Set a new (already hashed) password and consume the reset token in one update."""
        collection = self.get_players_collection()
        collection.update_one(
            {"email": email.lower()},
            {
                "$set": {"password": hashed_password},
                "$unset": {"reset_token_hash": "", "reset_token_expires": ""}
            }
        )
        self.logger.info(f"Password reset for player {email.lower()}")

    def update_player_profile(self, email: str, updates: dict) -> dict | None:
        """Apply a partial profile update and return the player document after the change.

        ``updates`` is trusted to contain only editable, already-validated fields.
        """
        collection = self.get_players_collection()
        if not updates:
            return collection.find_one({"email": email.lower()})

        if updates.get("email"):
            updates["email"] = updates["email"].lower()

        updated = collection.find_one_and_update(
            {"email": email.lower()},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        if updated:
            updated["_id"] = str(updated["_id"])
            self.logger.info(f"Profile updated for player {email.lower()}")
        return updated

    def get_league_by_player_email(self, email_id: str):
        collection = self.get_players_collection()
        pipeline = [
            {"$match": {"email": email_id.lower()}},
            {"$unwind": "$leagues"},
            {
                "$lookup": {
                    "from": "league",
                    "localField": "leagues.league_id",
                    "foreignField": "league_id",
                    "as": "league_details"
                }
            },
            {
                "$addFields": {
                    "leagues.rounds": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$league_details.rounds", 0]}, []
                        ]
                    }
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "leagues": {"$push": "$leagues"}
                }
            },
            {"$project": {"leagues": 1, "_id": 0}}
        ]
        
        result = list(collection.aggregate(pipeline))
        return result[0] if result else None
