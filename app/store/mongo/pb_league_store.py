from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection

import logging

from app.vo.pb.league import League

logging.basicConfig(
    level=logging.INFO,  # Only output messages at INFO level and above
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PBLeagueStore:
    def __init__(self, mongo_uri="mongodb://localhost:27017/?directConnection=true", db_name="pickleball"):
        uri = "mongodb+srv://yogender_db_user:egyFPoU9emubk13N@cluster0.ggoh6bt.mongodb.net/?appName=Cluster0"
        # self.client = MongoClient(mongo_uri)
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.logger = logging.getLogger(__name__)

    def get_league_collection(self) -> Collection:
        collection_name = "league"
        return self.db[collection_name]

    def store_new_league_details(self, league_details: League):
        collection = self.get_league_collection()
        collection.insert_one(league_details.model_dump())

        # Update each player's leagues list
        league_data = {
            "league_id": str(league_details.league_id),
            "league_name": league_details.league_name,
            "league_type": "PB",  # Default type
            "league_status": league_details.status,
            "league_start_date": league_details.league_start_date,
            "league_end_date": league_details.league_end_date
        }
        self.bulk_update_players_league_details(league_details.player_emails, league_data)

        self.logger.info("Successfully inserted league details and updated player records.")

    def bulk_update_players_league_details(self, emails: list[str], league_data: dict):
        """
        Update or add a league entry for multiple players at once.
        """
        collection = self.get_players_collection()
        league_id = league_data["league_id"]
        emails = [e.lower() for e in emails]

        collection.update_many(
            {"email": {"$in": emails}, "leagues.league_id": league_id},
            {"$set": {
                "leagues.$.league_name": league_data.get("league_name"),
                "leagues.$.league_type": league_data.get("league_type"),
                "leagues.$.league_status": league_data.get("league_status"),
                "leagues.$.league_start_date": league_data.get("league_start_date"),
                "leagues.$.league_end_date": league_data.get("league_end_date")
            }}
        )

        # # 2. Add new league entries for players who don't have this league_id yet
        # # This is more complex in a single query, so we do it for players where it wasn't updated
        # # Find players from the list who DON'T have this league_id
        # # Actually, simpler to just $addToSet if not exists, but MongoDB 
        # # doesn't easily do "push if not exists in array by specific field" in update_many without arrayFilters

        # # Alternative: use $push if it doesn't exist
        # for email in emails:
        #     collection.update_one(
        #         {"email": email, "leagues.league_id": {"$ne": league_id}},
        #         {"$push": {"leagues": league_data}}
        #     )

    def get_league_details(self, league_id: str):
        collection = self.get_league_collection()
        return collection.find_one({"league_id": league_id})

    def update_league_details(self, league_id: str, league_details: League):
        collection = self.get_league_collection()
        collection.update_one({"league_id": league_id}, {"$set": league_details.model_dump()})
        self.logger.info("Successfully updated league details.")

    def get_all_leagues(self) -> list[dict]:
        collection = self.get_league_collection()
        leagues = list(collection.find({}, {"league_name": 1, "status": 1, "_id": 0}))
        return [{"league_name": league["league_name"], "league_status": league.get("status")} for league in leagues]

    def get_league_by_status(self, status: str):
        collection = self.get_league_collection()
        return list(collection.find({"status": status}))
