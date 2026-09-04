import logging
import uuid
from datetime import datetime

from app.services.tournament_bracket import (
    advance_knockout,
    build_knockout,
    build_pools,
    build_team_pools,
    knockout_is_complete,
    resolve_pool_qualifiers,
)
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.player import Player
from app.vo.pb.tournament import KnockoutRound, Pool, Tournament
from app.vo.pb.tournament_match_score_payload import TournamentMatchScorePayload
from app.vo.pb.tournament_registration_payload import TournamentRegistrationPayload
from app.vo.pb.tournament_team import TournamentTeam

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
        # Pools and the knockout bracket are built later, by generate_draw(),
        # once registration is closed — not on every roster change.
        return self._store_and_return(tournament)

    def _store_and_return(self, tournament: Tournament) -> Tournament:
        self.pb_tournament_store.store_new_tournament(tournament)
        return tournament

    # ------------------------------------------------------------------ reads

    def get_all_tournaments(self) -> list[dict]:
        return self.pb_tournament_store.get_all_tournaments()

    def get_tournaments_by_club(self, club_id: str) -> list[dict]:
        return self.pb_tournament_store.get_tournaments_by_club(club_id)

    def get_tournaments_by_player_email(self, email: str) -> list[dict]:
        return self.pb_tournament_store.get_tournaments_by_player_email(email)

    def get_tournament_by_id(self, tournament_id: str):
        return self.pb_tournament_store.get_tournament_details(tournament_id)

    def get_matches_by_player_email(self, email: str) -> list[dict]:
        """Flatten pool + knockout matches from every tournament the player is
        registered in, resolved to the player's own email, in the same nested
        team_one/team_two -> player_one/player_two shape league matches use.
        """
        email_lower = (email or "").lower()
        matches: list[dict] = []
        for tournament in self.pb_tournament_store.get_tournaments_containing_player(email_lower):
            team_map = {t["team_id"]: t for t in (tournament.get("teams") or [])}
            for pool in tournament.get("pools") or []:
                for match in pool.get("matches") or []:
                    normalized = self._normalize_tournament_match(
                        tournament, team_map, match, stage="pool", email_lower=email_lower
                    )
                    if normalized:
                        matches.append(normalized)
            for round_ in tournament.get("knockout") or []:
                for match in round_.get("matches") or []:
                    normalized = self._normalize_tournament_match(
                        tournament, team_map, match, stage="knockout", email_lower=email_lower
                    )
                    if normalized:
                        matches.append(normalized)
        return matches

    @staticmethod
    def _split_name(name: str) -> tuple[str, str]:
        parts = (name or "").strip().split(" ", 1)
        return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")

    def _resolve_side(self, participant_email, participant_name, team_map: dict) -> dict:
        """Build a team_one/team_two-shaped dict for one side of a tournament match."""
        if not participant_email:
            return {"team_name": "TBD", "score": None, "player_one": None, "player_two": None}

        team = team_map.get(participant_email)
        if team:
            first1, last1 = self._split_name(team.get("player_one_name"))
            side = {
                "team_name": team.get("team_name"),
                "player_one": {
                    "email": team.get("player_one_email"),
                    "firstName": first1,
                    "lastName": last1,
                },
                "player_two": None,
            }
            if team.get("player_two_email"):
                first2, last2 = self._split_name(team.get("player_two_name"))
                side["player_two"] = {
                    "email": team.get("player_two_email"),
                    "firstName": first2,
                    "lastName": last2,
                }
            return side

        # Singles: participant_email is the player's own email.
        first, last = self._split_name(participant_name)
        return {
            "team_name": participant_name,
            "player_one": {"email": participant_email, "firstName": first, "lastName": last},
            "player_two": None,
        }

    def _normalize_tournament_match(
        self, tournament: dict, team_map: dict, match: dict, stage: str, email_lower: str
    ) -> dict | None:
        team_one = self._resolve_side(
            match.get("participant_one_email"), match.get("participant_one_name"), team_map
        )
        team_two = self._resolve_side(
            match.get("participant_two_email"), match.get("participant_two_name"), team_map
        )

        involved_emails = {
            (p.get("email") or "").lower()
            for side in (team_one, team_two)
            for p in (side.get("player_one"), side.get("player_two"))
            if p and p.get("email")
        }
        if email_lower not in involved_emails:
            return None

        team_one["score"] = match.get("score_one", 0)
        team_two["score"] = match.get("score_two", 0)

        return {
            "source": "tournament",
            "tournament_id": tournament.get("tournament_id"),
            "tournament_name": tournament.get("tournament_name"),
            "league_id": None,
            "match_id": match.get("match_id"),
            "stage": stage,
            "team_one": team_one,
            "team_two": team_two,
            "match_status": match.get("match_status"),
            "location": tournament.get("location"),
            # Individual matches aren't scheduled to a specific time; fall back
            # to the tournament's start date so the UI still has something to show.
            "time": self._parse_tournament_date(tournament.get("tournament_start_date")),
        }

    @staticmethod
    def _parse_tournament_date(date_str: str | None):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%m-%d-%Y")
        except ValueError:
            return None

    def delete_tournament(self, tournament_id: str) -> bool:
        return self.pb_tournament_store.delete_tournament(tournament_id)

    # ---------------------------------------------------------- registration

    def register(
        self, tournament_id: str, payload: TournamentRegistrationPayload, email: str
    ) -> None:
        """Register a player for a tournament.

        Singles: just the player. Doubles: the player must name a partner
        (existing account), invite one by email, or flag that they are looking
        for a partner. Players whose DUPR rating falls outside the tournament's
        range are rejected (and so is a named partner).
        """
        email = (email or "").lower()
        doc = self.pb_tournament_store.get_tournament_details(tournament_id)
        if not doc:
            raise ValueError(f"Tournament with ID {tournament_id} not found")
        if (doc.get("tournament_status") or "pending") != "pending":
            raise ValueError("Registration is closed for this tournament")

        registrations = doc.get("registrations") or []
        taken = self._registered_emails(registrations)
        if email in taken:
            raise ValueError("You are already registered for this tournament")

        player_doc = PBPlayerStore().find_player_by_email(email)
        if not player_doc:
            raise ValueError(f"Player with email {email} not found")

        dupr_error = self._dupr_error(player_doc.get("dupr_rating"), doc, "Your")
        if dupr_error:
            raise ValueError(dupr_error)

        reg = {
            "firstName": player_doc["firstName"],
            "lastName": player_doc["lastName"],
            "email": player_doc["email"],
            "dupr_rating": player_doc.get("dupr_rating"),
            "needs_partner": False,
            "partner_email": None,
            "partner_name": None,
            "partner_dupr": None,
            "partner_registered": False,
            "team_id": None,
        }

        if (doc.get("match_format") or "doubles") == "doubles":
            self._apply_partner_choice(reg, payload, doc, email, taken)

        registrations.append(reg)
        self._persist_registrations(tournament_id, registrations)

    def _apply_partner_choice(self, reg, payload, doc, email, taken):
        choices = [
            bool(payload.partner_email),
            bool(payload.partner_invite_email),
            bool(payload.needs_partner),
        ]
        if sum(choices) != 1:
            raise ValueError(
                "Choose exactly one: name a partner, invite a partner by email, "
                "or register as looking for a partner"
            )

        if payload.partner_email:
            partner_email = payload.partner_email.lower()
            if partner_email == email:
                raise ValueError("You cannot partner with yourself")
            if partner_email in taken:
                raise ValueError("That player is already registered for this tournament")
            partner_doc = PBPlayerStore().find_player_by_email(partner_email)
            if not partner_doc:
                raise ValueError(
                    f"No player account found for {partner_email}. "
                    f"Use the 'invite by email' option instead."
                )
            partner_error = self._dupr_error(
                partner_doc.get("dupr_rating"), doc, "Your partner's"
            )
            if partner_error:
                raise ValueError(partner_error)
            reg.update(
                {
                    "partner_email": partner_doc["email"],
                    "partner_name": f"{partner_doc['firstName']} {partner_doc['lastName']}".strip(),
                    "partner_dupr": partner_doc.get("dupr_rating"),
                    "partner_registered": True,
                }
            )
        elif payload.partner_invite_email:
            invite_email = payload.partner_invite_email.lower()
            if invite_email == email:
                raise ValueError("You cannot partner with yourself")
            if invite_email in taken:
                raise ValueError("That player is already registered for this tournament")
            reg.update(
                {
                    "partner_email": invite_email,
                    "partner_name": (payload.partner_invite_name or "").strip() or invite_email,
                    "partner_dupr": None,
                    "partner_registered": False,
                }
            )
        else:
            reg["needs_partner"] = True

    def unregister_player(self, tournament_id: str, email: str) -> None:
        """Remove a player's registration (only while registration is open)."""
        email = (email or "").lower()
        doc = self.pb_tournament_store.get_tournament_details(tournament_id)
        if not doc:
            raise ValueError(f"Tournament with ID {tournament_id} not found")
        if (doc.get("tournament_status") or "pending") != "pending":
            raise ValueError("You can no longer withdraw from this tournament")

        registrations = doc.get("registrations") or []
        remaining = [
            r for r in registrations if (r.get("email") or "").lower() != email
        ]
        if len(remaining) == len(registrations):
            raise ValueError("You are not registered for this tournament")

        self._persist_registrations(tournament_id, remaining)

    # backwards-compatible alias used by older callers / seeders
    def register_player(self, tournament_id: str, email: str) -> None:
        self.register(
            tournament_id,
            TournamentRegistrationPayload(tournament_id=tournament_id, email=email, needs_partner=True),
            email,
        )

    # ----------------------------------------------------------------- draw

    def generate_draw(self, tournament_id: str) -> dict:
        """Close registration and build the pools + knockout bracket.

        For doubles, registrations without a partner are auto-paired by DUPR
        rating (highest first). An odd one out becomes a one-person team.
        """
        doc = self.pb_tournament_store.get_tournament_details(tournament_id)
        if not doc:
            raise ValueError(f"Tournament with ID {tournament_id} not found")
        if (doc.get("tournament_status") or "pending") != "pending":
            raise ValueError("The draw has already been generated for this tournament")

        registrations = doc.get("registrations") or []
        pool_size = doc.get("pool_size", 4)
        advancers = doc.get("advancers_per_pool", 2)
        fmt = doc.get("match_format") or "doubles"

        teams: list[TournamentTeam] = []
        if fmt == "singles":
            entrants = [Player(**p) for p in (doc.get("players") or [])]
            if len(entrants) < 2:
                raise ValueError("Need at least 2 registered players to generate the draw")
            pools = build_pools(entrants, pool_size)
            summary = {"format": "singles", "players": len(entrants)}
        else:
            solos = []
            for reg in registrations:
                if reg.get("partner_email"):
                    teams.append(self._team_from_registration(reg))
                else:
                    solos.append(reg)

            solos.sort(key=lambda r: (r.get("dupr_rating") or 0.0), reverse=True)
            auto_paired = 0
            for i in range(0, len(solos), 2):
                teams.append(self._auto_team(solos[i : i + 2]))
                auto_paired += 1

            if len(teams) < 2:
                raise ValueError("Need at least 2 teams to generate the draw")
            pools = build_team_pools(teams, pool_size)
            summary = {
                "format": "doubles",
                "teams": len(teams),
                "auto_paired": auto_paired,
                "unresolved_invites": sum(
                    1
                    for r in registrations
                    if r.get("partner_email") and not r.get("partner_registered")
                ),
            }

        knockout = build_knockout(len(pools), advancers)
        self.pb_tournament_store.update_tournament(
            tournament_id,
            {
                "registrations": registrations,
                "teams": [t.model_dump() for t in teams],
                "pools": [p.model_dump() for p in pools],
                "knockout": [r.model_dump() for r in knockout],
                "tournament_status": "active",
            },
        )
        summary["pools"] = len(pools)
        summary["knockout_rounds"] = len(knockout)
        return summary

    def reopen_registration(self, tournament_id: str) -> None:
        """Undo a draw: clear pools/teams/bracket and re-open registration."""
        doc = self.pb_tournament_store.get_tournament_details(tournament_id)
        if not doc:
            raise ValueError(f"Tournament with ID {tournament_id} not found")
        registrations = doc.get("registrations") or []
        for reg in registrations:
            reg["team_id"] = None
        self.pb_tournament_store.update_tournament(
            tournament_id,
            {
                "registrations": registrations,
                "teams": [],
                "pools": [],
                "knockout": [],
                "tournament_status": "pending",
            },
        )

    # --------------------------------------------------------------- scoring

    def record_match_score(
        self, tournament_id: str, payload: TournamentMatchScorePayload
    ) -> dict:
        """Record a pool or knockout match result, then advance the bracket:
        resolve pool qualifiers into the first knockout round and carry each
        knockout winner (and any byes) forward. Returns the updated tournament.
        """
        doc = self.pb_tournament_store.get_tournament_details(tournament_id)
        if not doc:
            raise ValueError(f"Tournament with ID {tournament_id} not found")
        if (doc.get("tournament_status") or "pending") not in ("active", "completed"):
            raise ValueError("Generate the draw before entering scores")

        pools = [Pool(**p) for p in (doc.get("pools") or [])]
        rounds = [KnockoutRound(**r) for r in (doc.get("knockout") or [])]

        if payload.stage == "pool":
            match = next(
                (m for p in pools for m in p.matches if m.match_id == payload.match_id),
                None,
            )
        else:
            match = next(
                (m for r in rounds for m in r.matches if m.match_id == payload.match_id),
                None,
            )
        if match is None:
            raise ValueError("Match not found in this tournament")

        if not (match.participant_one_email and match.participant_two_email):
            raise ValueError("Both participants must be decided before scoring this match")
        if payload.stage == "knockout" and payload.score_one == payload.score_two:
            raise ValueError("A knockout match needs a winner — scores can't be tied")

        match.score_one = payload.score_one
        match.score_two = payload.score_two
        match.match_status = "Completed"

        resolve_pool_qualifiers(pools, rounds, doc.get("advancers_per_pool", 2))
        advance_knockout(rounds)

        fields = {
            "pools": [p.model_dump() for p in pools],
            "knockout": [r.model_dump() for r in rounds],
        }
        if knockout_is_complete(rounds):
            fields["tournament_status"] = "completed"
        elif doc.get("tournament_status") == "completed":
            # an earlier result was corrected — the bracket is live again
            fields["tournament_status"] = "active"
        self.pb_tournament_store.update_tournament(tournament_id, fields)
        return self.pb_tournament_store.get_tournament_details(tournament_id)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _registered_emails(registrations: list[dict]) -> set:
        taken = set()
        for reg in registrations:
            taken.add((reg.get("email") or "").lower())
            if reg.get("partner_email"):
                taken.add(reg["partner_email"].lower())
        return taken

    @staticmethod
    def _dupr_error(rating, doc: dict, who: str) -> str | None:
        lo, hi = doc.get("dupr_min"), doc.get("dupr_max")
        if lo is None and hi is None:
            return None
        if rating is None:
            return f"{who} DUPR rating is required to register for this tournament"
        if lo is not None and rating < lo:
            return f"{who} DUPR rating {rating} is below this tournament's minimum of {lo}"
        if hi is not None and rating > hi:
            return f"{who} DUPR rating {rating} is above this tournament's maximum of {hi}"
        return None

    @staticmethod
    def _short(name: str) -> str:
        name = (name or "").strip()
        return name.split()[-1] if name else name

    def _roster(self, registrations: list[dict]) -> list[dict]:
        """Flat list of every individual participant, keyed by email."""
        seen: dict[str, dict] = {}
        for reg in registrations:
            seen[(reg.get("email") or "").lower()] = {
                "firstName": reg.get("firstName", ""),
                "lastName": reg.get("lastName", ""),
                "email": reg.get("email"),
                "dupr_rating": reg.get("dupr_rating"),
            }
            partner_email = reg.get("partner_email")
            if partner_email:
                parts = (reg.get("partner_name") or "").split(" ", 1)
                seen[partner_email.lower()] = {
                    "firstName": parts[0] if parts else "",
                    "lastName": parts[1] if len(parts) > 1 else "",
                    "email": partner_email,
                    "dupr_rating": reg.get("partner_dupr"),
                }
        return list(seen.values())

    def _persist_registrations(self, tournament_id: str, registrations: list[dict]) -> None:
        self.pb_tournament_store.update_tournament(
            tournament_id,
            {
                "registrations": registrations,
                "players": self._roster(registrations),
            },
        )

    def _team_from_registration(self, reg: dict) -> TournamentTeam:
        team_id = str(uuid.uuid4())
        reg["team_id"] = team_id
        ratings = [r for r in (reg.get("dupr_rating"), reg.get("partner_dupr")) if r is not None]
        avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        p1_name = f"{reg['firstName']} {reg['lastName']}".strip()
        p2_name = reg.get("partner_name") or reg.get("partner_email")
        return TournamentTeam(
            team_id=team_id,
            team_name=f"{self._short(reg.get('lastName') or p1_name)} / {self._short(p2_name)}",
            player_one_email=reg["email"],
            player_one_name=p1_name,
            player_two_email=reg.get("partner_email"),
            player_two_name=p2_name,
            dupr_rating=avg,
            formed_by="partner" if reg.get("partner_registered") else "invite",
        )

    def _auto_team(self, pair: list[dict]) -> TournamentTeam:
        team_id = str(uuid.uuid4())
        names, emails, ratings = [], [], []
        for reg in pair:
            reg["team_id"] = team_id
            reg["needs_partner"] = False
            names.append(f"{reg['firstName']} {reg['lastName']}".strip())
            emails.append(reg["email"])
            if reg.get("dupr_rating") is not None:
                ratings.append(reg["dupr_rating"])
        avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        return TournamentTeam(
            team_id=team_id,
            team_name=" / ".join(self._short(n) for n in names),
            player_one_email=emails[0],
            player_one_name=names[0],
            player_two_email=emails[1] if len(emails) > 1 else None,
            player_two_name=names[1] if len(names) > 1 else None,
            dupr_rating=avg,
            formed_by="auto",
        )
