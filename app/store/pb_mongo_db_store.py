from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection

import logging

from app.vo.pb.league import League

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class PBMongoDBStore:
    def __init__(self, mongo_uri="mongodb://localhost:27017/?directConnection=true", db_name="pickleball"):
        uri = "mongodb+srv://yogender_db_user:egyFPoU9emubk13N@cluster0.ggoh6bt.mongodb.net/?appName=Cluster0"
        # self.client = MongoClient(mongo_uri)
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_collection(self) -> Collection:
        collection_name = "pickleball"
        return self.db[collection_name]

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

    def store_new_league_details(self, league_details: League):
        collection = self.get_collection()
        collection.insert_one(league_details.model_dump())
        self.logger.info("Successfully inserted league details.")

   