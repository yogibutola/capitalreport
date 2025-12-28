from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection
from bson import ObjectId

import logging

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.league import League
from app.vo.pb.match_details_payload import MatchDetailsPayload
from app.vo.pb.slotting_details_payload import SlottingDetailsPayload

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
        league = collection.insert_one(league_details.model_dump())

        # Update each player's leagues list
        league_data = {
            "league_id": str(league.inserted_id),
            "league_name": league_details.league_name,
            "league_type": "PB",  # Default type
            "league_status": league_details.league_status,
            "league_start_date": league_details.league_start_date,
            "league_end_date": league_details.league_end_date
        }
        league_details.league_id = league.inserted_id
        pb_player_store = PBPlayerStore()
        pb_player_store.bulk_update_players_league_details(league_details.player_emails, league_data)

        self.logger.info("Successfully inserted league details and updated player records.")

    def get_league_details(self, league_id: str):
        collection = self.get_league_collection()
        return collection.find_one({"league_id": league_id})

    def update_league_details(self, league_id: str, league_details: League):
        collection = self.get_league_collection()
        collection.update_one({"league_id": league_id}, {"$set": league_details.model_dump()})
        self.logger.info("Successfully updated league details.")

    def get_all_leagues(self) -> list[dict]:
        collection = self.get_league_collection()
        leagues = list(collection.find({}, {"league_name": 1, "league_status": 1, "status": 1, "_id": 1}))
        return [
            {"league_name": league["league_name"], "league_status": league.get("league_status") or league.get("status"),
             "league_id": str(league.get("_id"))} for league in leagues]

    def get_league_by_status(self, status: str):
        collection = self.get_league_collection()
        return list(collection.find({"$or": [{"league_status": status}, {"status": status}]}))

    def get_players_by_league_id(self, league_id: str):
        collection = self.get_league_collection()
        league = collection.find_one({"_id": ObjectId(league_id)}, {"players": 1})
        return league.get("players", []) if league else []

    def update_league_with_round_details(self, slotting_details: SlottingDetailsPayload):
        collection = self.get_league_collection()
        # Use exclude_unset=True to only update the fields provided in the request
        update_data = slotting_details.model_dump(exclude_unset=True)
        # We don't want to update the _id field itself
        if "_id" in update_data:
            del update_data["_id"]
        if "league_id" in update_data:
            del update_data["league_id"]

        collection.update_one({"_id": ObjectId(slotting_details.league_id)}, {"$set": update_data})
        self.logger.info(f"Successfully updated league details for ID: {slotting_details.league_id}")

    def get_league_details_by_league_name(self, league_name: str):
        collection = self.get_league_collection()
        return collection.find_one({"league_name": league_name}, {"_id": 0})

    def save_match_score(self, match_details: MatchDetailsPayload):
        collection = self.get_league_collection()
        collection.update_one(
            {"league_name": match_details.league_name},
            {"$set": {
                "rounds.$[r].group.$[g].match.$[m].team_one.score": match_details.score_team_1,
                "rounds.$[r].group.$[g].match.$[m].team_two.score": match_details.score_team_2
            }},
            array_filters=[
                {"r.round_id": match_details.round_id},
                {"g.group_id": match_details.group_id},
                {"m.match_id": match_details.match_id}
            ]
        )
