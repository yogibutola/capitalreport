from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection
import logging
from typing import List
from app.vo.pb.match import Match
from app.vo.pb.match_details_payload import MatchDetailsPayload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class PBMatchStore:
    def __init__(self, mongo_uri="mongodb://localhost:27017/?directConnection=true", db_name="pickleball"):
        uri = "mongodb+srv://yogender_db_user:egyFPoU9emubk13N@cluster0.ggoh6bt.mongodb.net/?appName=Cluster0"
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_matches_collection(self) -> Collection:
        collection_name = "matches"
        return self.db[collection_name]

    def store_match_details(self, matches: List[Match]):
        """
        Store match details in the matches collection.
        Updates existing matches if match_id already exists.
        """
        collection = self.get_matches_collection()
        for match in matches:
            match_data = match.model_dump()
            # We use match_id as a unique identifier if possible,
            # or a combination of league_id, round_id, group_id, match_id
            collection.update_one(
                {
                    "league_id": match.league_id,
                    "round_id": match.round_id,
                    "group_id": match.group_id,
                    "match_id": match.match_id
                },
                {"$set": match_data},
                upsert=True
            )
        self.logger.info(f"Successfully stored {len(matches)} match details.")

    def save_match_score(self, match_details: MatchDetailsPayload):
        collection = self.get_matches_collection()
        collection.update_one(
            {
                "match_id": match_details.match_id,
                "league_id": match_details.league_id
            },
            {"$set": {
                "team_one.score": match_details.score_team_1,
                "team_two.score": match_details.score_team_2,
                "match_status": match_details.match_status
            }}
        )

    def get_match_details_by_league_id(self, league_id: str):
        collection = self.get_matches_collection()
        return list(collection.find({"league_id": str(league_id)}))