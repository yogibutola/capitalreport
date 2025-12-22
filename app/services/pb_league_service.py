from app.store.pb_mongo_db_store import PBMongoDBStore
from app.vo.pb.league import League

class PBLeagueService:
    def __init__(self, mongo_db_store: PBMongoDBStore):
        self.mongo_db_store = mongo_db_store

    def get_league_details(self):
        return "League details" 

    def get_player_details(self):
        return "Player details"

    def get_match_details(self):
        return "Match details"

    def get_team_details(self):
        return "Team details"


    def get_player_stats(self):
        return "Player stats"

    def get_team_stats(self):
        return "Team stats"

    def get_match_stats(self):
        return "Match stats"

    def get_player_match_stats(self):
        return "Player match stats"

    def get_team_match_stats(self):
        return "Team match stats"

    def save_league_details(self, league_details: League):
        self.mongo_db_store.store_new_league_details(league_details)