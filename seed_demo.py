"""Seed the read-only demo data that the home page "Demo" buttons sign into.

Creates (idempotently — safe to re-run):

  * a demo club/admin account   demo.club@stackedpaddle.com
  * a demo player account        demo.player@stackedpaddle.com   <- visitors log in as this
  * 40 filler player accounts    demo.p01@stackedpaddle.com ... demo.p40@stackedpaddle.com
  * one league owned by the demo club (demo player + 11 fillers), round 1 slotted
    and fully scored so standings + promotion/relegation + round 2 are all
    visible, with the demo player as a participant
  * one doubles tournament owned by the demo club: 40 players -> 20 teams, draw
    generated and pool matches scored, with the demo player on a team

The accounts have real passwords too (see PASSWORD below) but the product path
is POST /api/v1/demo-signin {"persona": "admin"|"player"}, which mints a token
carrying a "demo" claim. app/api/v1/deps.py rejects every write request made
with such a token, so this data never degrades.

Usage:
    export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
    python seed_demo.py

Run once per environment (locally, and once against the Cloud Run Mongo after
deploy — the URI is in Secret Manager).
"""
import os
import sys

from fastapi import HTTPException
from faker import Faker

from app.services.pb_league_service import PBLeagueService
from app.services.pb_player_service import PBPlayerService, DEMO_ACCOUNTS
from app.services.pb_tournament_service import PBTournamentService
from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_match_store import PBMatchStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.league import League
from app.vo.pb.match_details_payload import MatchDetailsPayload
from app.vo.pb.player import ClubSignup, PlayerSignup
from app.vo.pb.tournament import Tournament
from app.vo.pb.tournament_match_score_payload import TournamentMatchScorePayload
from app.vo.pb.tournament_registration_payload import TournamentRegistrationPayload

PASSWORD = "Demo@1234"
DEMO_ADMIN_EMAIL = DEMO_ACCOUNTS["admin"]
DEMO_PLAYER_EMAIL = DEMO_ACCOUNTS["player"]
DEMO_CLUB_NAME = "StackedPaddle Demo Club"
# Enough for a 12-player league and a 40-player (20-team) doubles tournament.
FILLER_COUNT = 40
LEAGUE_FILLERS = 11        # + the demo player = 12 -> three groups of four
TOURNAMENT_PLAYERS = 40    # demo player + 39 fillers -> 20 doubles teams


def _player_service() -> PBPlayerService:
    return PBPlayerService(PBPlayerStore())


def _mark_demo(email: str) -> None:
    """Tag an account so a future reseed can find demo-created data."""
    PBPlayerStore().get_players_collection().update_one(
        {"email": email.lower()}, {"$set": {"is_demo": True}}
    )


def _ensure_player(first: str, last: str, email: str, dupr: float) -> None:
    try:
        _player_service().register_player(
            PlayerSignup(firstName=first, lastName=last, email=email,
                         password=PASSWORD, dupr_rating=dupr)
        )
        print(f"  created player {email}")
    except HTTPException as e:
        if e.status_code == 409:
            print(f"  player {email} already exists")
        else:
            raise
    _mark_demo(email)


def _ensure_accounts() -> list[str]:
    print("--- Accounts ---")
    # Demo club (admin)
    try:
        _player_service().register_club(
            ClubSignup(clubName=DEMO_CLUB_NAME, email=DEMO_ADMIN_EMAIL,
                       password=PASSWORD, address="123 Baseline Ct, Portland OR",
                       phone="555-0100")
        )
        print(f"  created club {DEMO_ADMIN_EMAIL}")
    except HTTPException as e:
        if e.status_code == 409:
            print(f"  club {DEMO_ADMIN_EMAIL} already exists")
        else:
            raise
    _mark_demo(DEMO_ADMIN_EMAIL)

    # The account visitors sign in as for the player demo.
    _ensure_player("Demo", "Player", DEMO_PLAYER_EMAIL, 3.5)

    # Filler players — deterministic faker names, stable emails.
    fillers = []
    for i in range(1, FILLER_COUNT + 1):
        fake = Faker()
        fake.seed_instance(f"demo-seed-{i}")
        email = f"demo.p{i:02d}@stackedpaddle.com"
        _ensure_player(fake.first_name(), fake.last_name(), email,
                       round(2.8 + (i / FILLER_COUNT) * 1.8, 2))
        fillers.append(email)
    return fillers


def _wipe_previous() -> None:
    """Delete any league/tournament the demo club owns, so a re-run is clean."""
    print("--- Clearing previous demo league/tournament ---")
    league_store = PBLeagueStore()
    league_service = PBLeagueService(league_store)
    for lg in league_service.get_leagues_by_club(DEMO_ADMIN_EMAIL):
        lid = lg.get("league_id") or str(lg.get("_id"))
        league_service.delete_league(lid)
        print(f"  deleted league {lid}")

    tournament_service = PBTournamentService(PBTournamentStore())
    for t in tournament_service.get_tournaments_by_club(DEMO_ADMIN_EMAIL):
        tid = t.get("tournament_id")
        tournament_service.delete_tournament(tid)
        print(f"  deleted tournament {tid}")

    # Drop stale league references from the demo accounts so a re-run starts clean.
    PBPlayerStore().get_players_collection().update_many(
        {"is_demo": True}, {"$set": {"leagues": []}}
    )


def _seed_league(participant_emails: list[str]) -> str:
    print("--- League ---")
    league_store = PBLeagueStore()
    service = PBLeagueService(league_store)

    league = League(
        league_name="StackedPaddle Demo League",
        league_description="A sample league so you can explore rounds, slotting and standings.",
        league_start_date="01-15-2026",
        league_duration="8",
        group_size=4,
        match_format="Doubles",
        league_status="Active",
        club_id=DEMO_ADMIN_EMAIL,
    )
    service.save_league_details(league)
    league_id = str(league.league_id)
    print(f"  created league {league_id}")

    for email in participant_emails:
        service.register_player(league_id, email)
    print(f"  registered {len(participant_emails)} players")

    service.slot_first_round_of_day(league_id, 1)
    print("  slotted round 1")

    # Score every round-1 match. Completing all groups auto-triggers
    # promotion/relegation and slotting of round 2.
    matches = PBMatchStore().get_match_details_by_league_id(league_id)
    round_one = [m for m in matches if int(m.get("round_id", 0)) == 1]
    for idx, m in enumerate(round_one):
        team_one_wins = idx % 2 == 0
        service.save_match_score(MatchDetailsPayload(
            league_id=league_id,
            match_id=m["match_id"],
            score_team_1=11 if team_one_wins else 7,
            score_team_2=7 if team_one_wins else 11,
            match_status="completed",
        ))
    print(f"  scored {len(round_one)} round-1 matches")
    return league_id


def _seed_tournament(pairs: list[tuple[str, str]]) -> str:
    print("--- Tournament ---")
    service = PBTournamentService(PBTournamentStore())

    tournament = Tournament(
        tournament_name="StackedPaddle Demo Open",
        tournament_description="A sample doubles tournament: pools, DUPR division, and a knockout bracket.",
        tournament_start_date="02-21-2026",
        match_format="doubles",
        dupr_min=2.5,
        dupr_max=5.5,
        pool_size=4,
        advancers_per_pool=2,
        tournament_status="pending",
        club_id=DEMO_ADMIN_EMAIL,
        players=[],
    )
    service.create_tournament(tournament)
    tournament_id = tournament.tournament_id
    print(f"  created tournament {tournament_id}")

    for captain, partner in pairs:
        service.register(
            tournament_id,
            TournamentRegistrationPayload(tournament_id=tournament_id,
                                          email=captain, partner_email=partner),
            captain,
        )
    print(f"  registered {len(pairs)} teams")

    service.generate_draw(tournament_id)
    print("  generated draw")

    # Score the round-robin pool matches so pool standings resolve and the
    # knockout bracket seeds. Leave the knockout partly played ("in progress").
    doc = service.get_tournament_by_id(tournament_id) or {}
    scored = 0
    for pool in doc.get("pools", []):
        for i, match in enumerate(pool.get("matches", [])):
            if not (match.get("participant_one_email") and match.get("participant_two_email")):
                continue
            one_wins = i % 2 == 0
            try:
                service.record_match_score(tournament_id, TournamentMatchScorePayload(
                    match_id=match["match_id"],
                    stage="pool",
                    score_one=11 if one_wins else 6,
                    score_two=6 if one_wins else 11,
                ))
                scored += 1
            except ValueError as e:
                print(f"    skipped a pool match: {e}")
    print(f"  scored {scored} pool matches")
    return tournament_id


def main() -> None:
    if not os.getenv("MONGO_URI"):
        print("MONGO_URI is not set. Export it first, e.g.\n"
              '  export MONGO_URI="mongodb://localhost:27017/?directConnection=true"')
        sys.exit(1)

    fillers = _ensure_accounts()
    _wipe_previous()

    # League: demo player + fillers -> three groups of four.
    league_players = [DEMO_PLAYER_EMAIL] + fillers[:LEAGUE_FILLERS]
    league_id = _seed_league(league_players)

    # Tournament: TOURNAMENT_PLAYERS players -> half that many doubles teams. The
    # demo player captains the first team; the remaining fillers pair up.
    tournament_fillers = fillers[: TOURNAMENT_PLAYERS - 1]
    pairs = [(DEMO_PLAYER_EMAIL, tournament_fillers[0])]
    rest = tournament_fillers[1:]
    pairs += [(rest[i], rest[i + 1]) for i in range(0, len(rest) - 1, 2)]
    tournament_id = _seed_tournament(pairs)

    print("\n==============================================")
    print("Demo data ready.")
    print(f"  Admin demo : POST /api/v1/demo-signin  {{'persona': 'admin'}}   ({DEMO_ADMIN_EMAIL})")
    print(f"  Player demo : POST /api/v1/demo-signin  {{'persona': 'player'}}  ({DEMO_PLAYER_EMAIL})")
    print(f"  League      : {league_id}")
    print(f"  Tournament  : {tournament_id}")
    print(f"  (password login also works: <email> / {PASSWORD})")
    print("==============================================")


if __name__ == "__main__":
    main()
