from bson import ObjectId
from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.league import League
from app.vo.pb.match import Match
from app.vo.pb.match_details_payload import MatchDetailsPayload
from app.vo.pb.slotting_details_payload import SlottingDetailsPayload
from app.store.mongo.pb_match_store import PBMatchStore



class PBLeagueService:
    def __init__(self, pb_league_store: PBLeagueStore):
        self.pb_league_store = pb_league_store
        self.pb_match_store = PBMatchStore()

    def get_league_details(self):
        return "League details"

    def get_match_details(self):
        return "Match details"

    def get_team_details(self):
        return "Team details"

    def get_team_stats(self):
        return "Team stats"

    def get_match_stats(self):
        return "Match stats"

    def get_player_match_stats(self):
        return "Player match stats"

    def get_team_match_stats(self):
        return "Team match stats"

    def save_league_details(self, league_details: League):
        self.pb_league_store.store_new_league_details(league_details)

    def get_all_leagues(self) -> list[dict]:
        return self.pb_league_store.get_all_leagues()

    def get_league_by_status(self, league_status: str):
        return self.pb_league_store.get_league_by_status(league_status)

    def get_players_by_league_id(self, league_id: str):
        return self.pb_league_store.get_players_by_league_id(league_id)

    def update_league_with_round_details(self, slotting_details: SlottingDetailsPayload):
        self.pb_league_store.update_league_with_round_details(slotting_details)
        
        # Extract match details from the slotting details
        matches = []
        for round_item in slotting_details.rounds:
            for group_item in round_item.group:
                for match_item in group_item.match:
                    matches.append(match_item)
        
        self.pb_match_store.store_match_details(matches)

    def get_league_details_by_league_name(self, league_name: str):
        return self.pb_league_store.get_league_details_by_league_name(league_name)

    def save_match_score(self, match_details: MatchDetailsPayload):
        self.pb_match_store.save_match_score(match_details)

    def register_player(self, league_id: str, email: str):
        # 1. Fetch player details
        pb_player_store = PBPlayerStore()
        player_doc = pb_player_store.find_player_by_email(email)
        if not player_doc:
            raise ValueError(f"Player with email {email} not found")

        # 2. Fetch league details
        league_collection = self.pb_league_store.get_league_collection()
        league_doc = league_collection.find_one({"_id": ObjectId(league_id)})
        if not league_doc:
            raise ValueError(f"League with ID {league_id} not found")

        # 3. Add player to league collection
        player_data = {
            "firstName": player_doc["firstName"],
            "lastName": player_doc["lastName"],
            "email": player_doc["email"],
            "dupr_rating": player_doc.get("dupr_rating")
        }
        self.pb_league_store.add_player_to_league(league_id, player_data)

        # 4. Update player record with league info
        league_info = {
            "league_id": str(league_doc["_id"]),
            "league_name": league_doc["league_name"],
            "league_type": league_doc.get("league_type", "PB"),
            "league_status": league_doc.get("league_status") or league_doc.get("status"),
            "league_start_date": league_doc.get("league_start_date"),
            "league_end_date": league_doc.get("league_end_date")
        }
        pb_player_store.bulk_update_players_league_details([email], league_info)