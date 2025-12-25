from app.store.mongo.pb_league_store import PBLeagueStore
from app.vo.pb.league import League

class PBLeagueService:
    def __init__(self, pb_league_store: PBLeagueStore):
        self.pb_league_store = pb_league_store

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

    def get_all_leagues(self)->list[dict]:
        return self.pb_league_store.get_all_leagues()

    def get_league_by_status(self, league_status: str):
        return self.pb_league_store.get_league_by_status(league_status)  

    def get_players_by_league_id(self, league_id: str):
        return self.pb_league_store.get_players_by_league_id(league_id)
        