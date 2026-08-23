from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection
import logging
import os
from typing import List
from app.vo.pb.match import Match
from app.vo.pb.match_details_payload import MatchDetailsPayload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class PBMatchStore:
    def __init__(self, mongo_uri=None, db_name="pickleball"):
        uri = mongo_uri or os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI environment variable must be set")
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
        match = self.get_match(match_details.league_id, match_details.match_id)
        
        # default assignment (assumes frontend sent team1/team2 in order)
        s1 = match_details.score_team_1
        s2 = match_details.score_team_2

        # if we provided team names, match them up to the backend representation
        if match and match_details.team_1_name and match_details.team_2_name:
            team_one_name = match.get("team_one", {}).get("team_name")
            team_two_name = match.get("team_two", {}).get("team_name")
            
            # if the payload's team 1 is actually team two on the backend
            if team_two_name == match_details.team_1_name or team_one_name == match_details.team_2_name:
                s1 = match_details.score_team_2
                s2 = match_details.score_team_1

        collection.update_one(
            {
                "match_id": match_details.match_id,
                "league_id": match_details.league_id
            },
            {"$set": {
                "team_one.score": s1,
                "team_two.score": s2,
                "match_status": match_details.match_status
            }}
        )

    def get_match_details_by_league_id(self, league_id: str):
        collection = self.get_matches_collection()
        return list(collection.find({"league_id": str(league_id)}))

    def get_matches_by_player_email(self, email: str) -> List[dict]:
        """Get all matches across all leagues where the player participates."""
        collection = self.get_matches_collection()
        email_lower = email.lower()
        return list(collection.find({
            "$or": [
                {"team_one.player_one.email": email_lower},
                {"team_one.player_two.email": email_lower},
                {"team_two.player_one.email": email_lower},
                {"team_two.player_two.email": email_lower}
            ]
        }))

    def get_matches_by_group(self, league_id: str, round_id: int, group_id: int) -> List[dict]:
        collection = self.get_matches_collection()
        return list(collection.find({
            "league_id": league_id,
            "round_id": round_id,
            "group_id": group_id
        }))

    def get_match(self, league_id: str, match_id: str) -> dict:
        collection = self.get_matches_collection()
        return collection.find_one({
            "league_id": league_id,
            "match_id": match_id
        })

    def delete_matches_by_league(self, league_id: str):
        collection = self.get_matches_collection()
        result = collection.delete_many({"league_id": str(league_id)})
        self.logger.info(f"Successfully deleted matches for league {league_id}. Deleted count: {result.deleted_count}")
        return result.deleted_count