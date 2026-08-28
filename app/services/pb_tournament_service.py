import logging

from app.services.tournament_bracket import build_knockout, build_pools
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.tournament import Tournament

logger = logging.getLogger(__name__)


class PBTournamentService:
    def __init__(self, pb_tournament_store: PBTournamentStore):
        self.pb_tournament_store = pb_tournament_store

    def create_tournament(self, tournament: Tournament) -> Tournament:
        # Stamp the owning club's name and location onto the tournament so
        # listings can show who runs it and where, without a second lookup.
        if tournament.club_id and not (tournament.club_name and tournament.location):
            club = PBPlayerStore().find_player_by_email(tournament.club_id)
            if club:
                tournament.club_name = (
                    tournament.club_name or club.get("clubName") or club.get("firstName")
                )
                tournament.location = tournament.location or club.get("address")

        tournament.tournament_status = tournament.tournament_status or "pending"

        # Generate the round-robin pools and the knockout bracket skeleton
        # from the registered players.
        tournament.pools = build_pools(tournament.players, tournament.pool_size)
        tournament.knockout = build_knockout(
            len(tournament.pools), tournament.advancers_per_pool
        )

        self.pb_tournament_store.store_new_tournament(tournament)
        return tournament

    def get_all_tournaments(self) -> list[dict]:
        return self.pb_tournament_store.get_all_tournaments()

    def get_tournaments_by_club(self, club_id: str) -> list[dict]:
        return self.pb_tournament_store.get_tournaments_by_club(club_id)

    def get_tournament_by_id(self, tournament_id: str):
        return self.pb_tournament_store.get_tournament_details(tournament_id)

    def delete_tournament(self, tournament_id: str) -> bool:
        return self.pb_tournament_store.delete_tournament(tournament_id)
