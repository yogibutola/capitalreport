"""Business logic for the hidden application ("platform") admin console.

Everything here is reachable only through :func:`app.api.v1.deps.get_current_superadmin`.
It reuses the existing player/league/tournament stores and the club/player
registration paths in :class:`PBPlayerService`.
"""
import logging

from fastapi import HTTPException, status

from app.store.mongo.pb_audit_store import PBAuditStore
from app.store.mongo.pb_club_store import PBClubStore
from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ClubSignup, PlayerSignup

logger = logging.getLogger(__name__)


class PBPlatformService:
    def __init__(
        self,
        player_store: PBPlayerStore,
        league_store: PBLeagueStore,
        tournament_store: PBTournamentStore,
        audit_store: PBAuditStore,
        club_store: PBClubStore | None = None,
    ):
        self.player_store = player_store
        self.league_store = league_store
        self.tournament_store = tournament_store
        self.audit_store = audit_store
        self.club_store = club_store or PBClubStore()
        self.player_service = PBPlayerService(player_store, self.club_store)

    # ---- clubs -----------------------------------------------------------------

    def list_clubs(self) -> list[dict]:
        out = []
        for club in self.club_store.list_clubs():
            club_id = str(club["_id"])
            owner = self.player_store.find_player_by_id(club.get("owner_player_id")) or {}
            out.append({
                "id": club_id,
                # The owner's sign-in email - who to contact about the club.
                "email": owner.get("email") or club.get("contact_email") or "",
                "clubName": club.get("name"),
                "address": club.get("address"),
                "phone": club.get("phone"),
                "league_count": len(self.league_store.get_leagues_by_club(club_id)),
                "tournament_count": len(self.tournament_store.get_tournaments_by_club(club_id)),
            })
        out.sort(key=lambda c: (c["clubName"] or "").lower())
        return out

    def create_club(self, payload: ClubSignup) -> dict:
        created = self.player_service.register_club(payload)
        return created.model_dump()

    def delete_club(self, club_id: str) -> None:
        """Remove the club (and its venues). The owner keeps their player account;
        by decision, the club's leagues/tournaments are orphaned, not cascaded."""
        if not self.club_store.delete_club(club_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Club not found")

    # ---- players -------------------------------------------------------------

    def list_players(self) -> list[dict]:
        players = self.player_store.get_all_players()
        out = [{
            "id": str(p.get("_id")),
            "email": p.get("email", ""),
            "firstName": p.get("firstName"),
            "lastName": p.get("lastName"),
            "dupr_rating": p.get("dupr_rating"),
            "state": p.get("state"),
            "city": p.get("city"),
            # Shown in the console because "why isn't X in distance search?"
            # is almost always a missing ZIP.
            "zip_code": p.get("zip_code"),
            "league_count": len(p.get("leagues", []) or []),
        } for p in players]
        out.sort(key=lambda p: ((p["firstName"] or "").lower(), (p["lastName"] or "").lower()))
        return out

    def create_player(self, payload: PlayerSignup) -> dict:
        created = self.player_service.register_player(payload)
        return created.model_dump()

    def delete_player(self, email: str) -> dict:
        player = self.player_store.find_player_by_email(email)
        if not player or player.get("role") == "admin":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Player not found")
        club = self.club_store.get_club_by_owner(player["_id"])
        if club:
            # Deleting the owner would leave a club nobody can sign in to run.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"{email} runs {club.get('name')}; remove the club first",
            )
        self.player_store.delete_player_by_email(email)
        leagues_touched = self.league_store.purge_player(email)
        tournaments_touched = self.tournament_store.purge_player(email)
        return {
            "email": email,
            "leagues_updated": leagues_touched,
            "tournaments_updated": tournaments_touched,
        }

    # ---- observability -----------------------------------------------------

    def activity(self, *, actor=None, action=None, since=None, limit=200) -> list[dict]:
        return self.audit_store.query(actor=actor, action=action, since=since, limit=limit)

    def metrics(self) -> dict:
        role_counts = self.player_store.count_by_role()
        base = {
            "total_clubs": self.club_store.count_clubs(),
            "total_players": role_counts.get("player", 0),
            "total_leagues": len(self.league_store.get_all_leagues()),
            "total_tournaments": len(self.tournament_store.get_all_tournaments()),
            "actions_24h": 0,
            "active_actors_24h": 0,
            "signins_7d": 0,
            "errors_24h": 0,
        }
        try:
            base.update(self.audit_store.metrics())
        except Exception:  # pragma: no cover - metrics must not 500 the console
            logger.warning("Could not compute audit metrics", exc_info=True)
        return base
