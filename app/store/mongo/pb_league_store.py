from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.synchronous.collection import Collection
from bson import ObjectId

import logging

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.league import League
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
        return collection.find_one({"_id": ObjectId(league_id)})

    def update_league_details(self, league_id: str, league_details: League):
        collection = self.get_league_collection()
        collection.update_one({"_id": ObjectId(league_id)}, {"$set": league_details.model_dump()})
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
        return collection.find_one({"league_name": league_name})


    def add_player_to_league(self, league_id: str, player_data: dict):
        collection = self.get_league_collection()
        collection.update_one(
            {"_id": ObjectId(league_id)},
            {"$addToSet": {"players": player_data}}
        )
        self.logger.info(f"Successfully added player {player_data.get('email')} to league {league_id}")

    def add_players_to_round_group(self, league_id: str, round_id: int, group_id: int, players: list):
        collection = self.get_league_collection()
        # Complex update:
        # 1. Try to push to existing group
        # This requires the group to exist.
        # If we are unsure if Round or Group exists, we might need upsert logic or simple check-then-update.
        # Given Mongo dynamics, using arrayFilters is best for nested arrays.
        
        # Checking if round/group exists is safer for now.
        league = collection.find_one({"_id": ObjectId(league_id)})
        if not league: return
        
        rounds = league.get("rounds", [])
        # Find if round exists
        round_exists = False
        for r in rounds:
            if int(r.get("round_id", -1)) == round_id:
                round_exists = True
                # Check if group exists
                group_exists = False
                for g in r.get("group", []):
                    if int(g.get("group_id", -1)) == group_id:
                        group_exists = True
                        # Update this group
                        # In code, we can append to g["players"]
                        existing_emails = set(p.get("email") for p in g.get("players", []))
                        for p in players:
                            if p["email"] not in existing_emails:
                                g.setdefault("players", []).append(p)
                                existing_emails.add(p["email"])
                        break
                if not group_exists:
                    # Create group
                    new_group = {
                        "group_id": group_id,
                        "group_name": f"Group {group_id}",
                        "match": [],
                        "players": players
                    }
                    r.setdefault("group", []).append(new_group)
                break
        
        if not round_exists:
            # Create round
            new_group = {
                "group_id": group_id,
                "group_name": f"Group {group_id}",
                "match": [],
                "players": players
            }
            new_round = {
                "round_id": round_id,
                "group": [new_group]
            }
            rounds.append(new_round)
            
        # Update the whole rounds array
        collection.update_one(
            {"_id": ObjectId(league_id)},
            {"$set": {"rounds": rounds}}
        )

    def set_group_matches(self, league_id: str, round_id: int, group_id: int, matches: list):
        collection = self.get_league_collection()
        # Similar logic: read-modify-write for simplicity avoiding deep arrayFilter complexity
        league = collection.find_one({"_id": ObjectId(league_id)})
        if not league: return
        
        rounds = league.get("rounds", [])
        updated = False
        for r in rounds:
            if int(r.get("round_id", -1)) == round_id:
                for g in r.get("group", []):
                    if int(g.get("group_id", -1)) == group_id:
                        g["match"] = [m.model_dump() if hasattr(m, 'model_dump') else m for m in matches]
                        g["group_size"] = len(matches)
                        updated = True
                        break
                if updated: break
        
        if updated:
            collection.update_one(
                {"_id": ObjectId(league_id)},
                {"$set": {"rounds": rounds}}
            )

    def add_withdrawal(self, league_id: str, withdrawal_data: dict):
        collection = self.get_league_collection()
        collection.update_one(
            {"_id": ObjectId(league_id)},
            {"$push": {"withdrawals": withdrawal_data}}
        )
        self.logger.info(f"Successfully added withdrawal for {withdrawal_data.get('email')} for play day {withdrawal_data.get('play_day')} to league {league_id}")

    def delete_league(self, league_id: str):
        collection = self.get_league_collection()
        result = collection.delete_one({"_id": ObjectId(league_id)})
        self.logger.info(f"Successfully deleted league {league_id}. Deleted count: {result.deleted_count}")
        return result.deleted_count > 0

