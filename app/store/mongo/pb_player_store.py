from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection

import logging

from app.vo.pb.league import League

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBPlayerStore:
    def __init__(self, mongo_uri="mongodb://localhost:27017/?directConnection=true", db_name="pickleball"):
        uri = "mongodb+srv://yogender_db_user:egyFPoU9emubk13N@cluster0.ggoh6bt.mongodb.net/?appName=Cluster0"
        # self.client = MongoClient(mongo_uri)
        self.client = MongoClient(uri, server_api=ServerApi('1'))
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
        """Fetch all players from the database"""
        collection = self.get_players_collection()
        players = list(collection.find())
        for player in players:
            player["_id"] = str(player["_id"])
        return players

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
