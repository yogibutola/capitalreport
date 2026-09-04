import logging
import os

from bson import ObjectId
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection

from app.vo.pb.tournament import Tournament

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBTournamentStore:
    def __init__(self, mongo_uri=None, db_name="pickleball"):
        uri = mongo_uri or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI environment variable must be set")
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_tournament_collection(self) -> Collection:
        return self.db["tournament"]

    def store_new_tournament(self, tournament: Tournament):
        collection = self.get_tournament_collection()
        result = collection.insert_one(tournament.model_dump(exclude={"tournament_id"}))
        tournament.tournament_id = str(result.inserted_id)
        self.logger.info(f"Successfully inserted tournament {tournament.tournament_id}.")

    def get_tournament_details(self, tournament_id: str):
        collection = self.get_tournament_collection()
        doc = collection.find_one({"_id": ObjectId(tournament_id)})
        if doc:
            doc["tournament_id"] = str(doc.pop("_id"))
        return doc

    def get_all_tournaments(self) -> list[dict]:
        return [self._summary(t) for t in self._list_summaries({})]

    def get_tournaments_by_club(self, club_id: str) -> list[dict]:
        return [self._summary(t) for t in self._list_summaries({"club_id": club_id})]

    def get_tournaments_by_player_email(self, email: str) -> list[dict]:
        return [
            self._summary(t)
            for t in self._list_summaries({"players.email": email.lower()})
        ]

    def get_tournaments_containing_player(self, email: str) -> list[dict]:
        """Full tournament docs (pools/knockout/teams included) for tournaments
        the player is registered in — used to build their match history."""
        collection = self.get_tournament_collection()
        docs = list(collection.find({"players.email": email.lower()}))
        for doc in docs:
            doc["tournament_id"] = str(doc.pop("_id"))
        return docs

    def update_tournament(self, tournament_id: str, fields: dict) -> bool:
        collection = self.get_tournament_collection()
        result = collection.update_one(
            {"_id": ObjectId(tournament_id)}, {"$set": fields}
        )
        return result.matched_count > 0

    def _list_summaries(self, query: dict) -> list[dict]:
        collection = self.get_tournament_collection()
        projection = {
            "tournament_name": 1,
            "tournament_status": 1,
            "tournament_start_date": 1,
            "tournament_end_date": 1,
            "club_name": 1,
            "location": 1,
            "match_format": 1,
            "dupr_min": 1,
            "dupr_max": 1,
            "players": 1,
        }
        return list(collection.find(query, projection))

    @staticmethod
    def _summary(doc: dict) -> dict:
        return {
            "tournament_id": str(doc.get("_id")),
            "tournament_name": doc.get("tournament_name"),
            "tournament_status": doc.get("tournament_status"),
            "tournament_start_date": doc.get("tournament_start_date"),
            "tournament_end_date": doc.get("tournament_end_date"),
            "club_name": doc.get("club_name"),
            "location": doc.get("location"),
            "match_format": doc.get("match_format"),
            "dupr_min": doc.get("dupr_min"),
            "dupr_max": doc.get("dupr_max"),
            "player_count": len(doc.get("players", []) or []),
        }

    def delete_tournament(self, tournament_id: str) -> bool:
        collection = self.get_tournament_collection()
        result = collection.delete_one({"_id": ObjectId(tournament_id)})
        self.logger.info(
            f"Deleted tournament {tournament_id}. Deleted count: {result.deleted_count}"
        )
        return result.deleted_count > 0
