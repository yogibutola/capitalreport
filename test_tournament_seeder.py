"""Seed a test doubles tournament and register N players for it.

Mirrors test_data_seeder.py (the league seeder). Creates the players, creates a
pending doubles tournament with a DUPR range, then registers players through the
same PBTournamentService.register path the API uses, and finally generates the
draw.

By default every doubles registration is a fully-formed team: players pair up
with a real named partner (N players -> N/2 teams, no auto-pairing at draw
time). Pass --invites / --solos to mix in a few off-platform email invites and
looking-for-a-partner registrations (the solos get auto-paired by rating when
the draw is generated).

Usage:
    export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
    python test_tournament_seeder.py                        # 40 players -> 20 teams
    python test_tournament_seeder.py --invites 2 --solos 4  # 17 teams + 2 invites + 4 solos
    python test_tournament_seeder.py --players 24 --pool-size 6 --format singles
"""
import argparse
import random
import sys
from datetime import datetime

from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.services.pb_tournament_service import PBTournamentService
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.player import PlayerSignup
from app.vo.pb.tournament import Tournament
from app.vo.pb.tournament_registration_payload import TournamentRegistrationPayload

PASSWORD = "Password@123"

FIRST_NAMES = [
    "Aarav", "Priya", "Liam", "Sofia", "Noah", "Aisha", "Mateo", "Emma", "Kenji",
    "Zara", "Diego", "Nina", "Omar", "Leila", "Ravi", "Hana", "Marcus", "Yuki",
    "Amara", "Felix", "Ingrid", "Tariq", "Chloe", "Arjun", "Maya", "Lucas",
    "Freya", "Ibrahim", "Elena", "Wei", "Rosa", "Dmitri", "Ada", "Kofi", "Lena",
    "Pablo", "Nadia", "Theo", "Sana", "Bruno",
]
LAST_NAMES = [
    "Sharma", "Nguyen", "Okafor", "Rossi", "Kim", "Patel", "Silva", "Andersson",
    "Haddad", "Kowalski", "Mbeki", "Tanaka", "Fernandez", "Novak", "Reyes",
    "Bauer", "Costa", "Ali", "Larsen", "Ivanov", "Cohen", "Dubois", "Yamada",
    "Mensah", "Petrov", "Khan", "Moreau", "Singh", "Weber", "Diaz",
]


def main():
    parser = argparse.ArgumentParser(description="Seed a test tournament with registered players.")
    parser.add_argument("--players", type=int, default=40, help="Number of players to create and register")
    parser.add_argument("--pool-size", type=int, default=4, help="Target players per round-robin pool")
    parser.add_argument("--advancers", type=int, default=2, help="Players advancing from each pool to the knockout stage")
    parser.add_argument("--format", type=str, default="doubles", choices=["doubles", "singles"],
                        help="Tournament format")
    parser.add_argument("--invites", type=int, default=0,
                        help="Doubles: how many registrants invite an off-platform partner by email")
    parser.add_argument("--solos", type=int, default=0,
                        help="Doubles: how many registrants register looking for a partner (auto-paired at draw)")
    parser.add_argument("--dupr-min", type=float, default=2.5, help="Lowest DUPR rating allowed to register")
    parser.add_argument("--dupr-max", type=float, default=5.0, help="Highest DUPR rating allowed to register")
    parser.add_argument("--club", type=str, default="test_south@gmail.com",
                        help="Email of the existing admin/club account that will own the tournament")
    args = parser.parse_args()

    if args.players < 2:
        print("Need at least 2 players.")
        sys.exit(1)

    pb_player_store = PBPlayerStore()
    pb_player_service = PBPlayerService(pb_player_store)
    pb_tournament_service = PBTournamentService(PBTournamentStore())

    club = pb_player_store.find_player_by_email(args.club)
    if not club or club.get("role") != "admin":
        print(f"Club/admin account '{args.club}' not found (or not an admin). "
              f"Create it first (club signup) or pass --club with an existing admin email.")
        sys.exit(1)
    print(f"Owning club: {args.club} ({club.get('clubName') or club.get('firstName')})")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    print(f"--- Creating/Verifying {args.players} Players ---")
    emails = []
    for i in range(1, args.players + 1):
        # Seed per-index so names are random-looking but stable across re-runs
        # (existing players keep their original name anyway; email is the key).
        rng = random.Random(f"tourney-seeder-{i}")
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        email = f"tourney{i:02d}.player@test.com"

        signup = PlayerSignup(
            firstName=first_name,
            lastName=last_name,
            email=email,
            password=PASSWORD,
            # Spread DUPR ratings 2.5 - 5.0 so pool seeding has something to sort on.
            dupr_rating=round(2.5 + (i / args.players) * 2.5, 2),
        )
        try:
            pb_player_service.register_player(signup)
            print(f"Created player: {first_name} {last_name} <{email}>")
        except HTTPException as e:
            if e.status_code == 409:
                print(f"Player already exists: {email}")
            else:
                print(f"Error creating player {email}: {e.detail}")
                sys.exit(1)
        emails.append(email)

    print("\n--- Creating Tournament ---")
    today = datetime.now().strftime("%m-%d-%Y")
    tournament = Tournament(
        tournament_name=f"Seeded Open {timestamp}",
        tournament_description="Tournament created by test_tournament_seeder.py",
        tournament_start_date=today,
        match_format=args.format,
        dupr_min=args.dupr_min,
        dupr_max=args.dupr_max,
        pool_size=args.pool_size,
        advancers_per_pool=args.advancers,
        tournament_status="pending",
        club_id=args.club,
        # club_name / location are left blank on purpose: create_tournament fills
        # them from the owning club's record.
        players=[],
    )
    pb_tournament_service.create_tournament(tournament)
    tournament_id = tournament.tournament_id
    print(f"Created Tournament ID: {tournament_id} | Name: {tournament.tournament_name}")

    # Work out the doubles registration plan: most players pair up as real
    # named-partner teams; --invites / --solos carve a few off the end for the
    # other two code paths. `paired` must be even so every captain has a partner.
    invites = max(0, args.invites) if args.format == "doubles" else 0
    solos = max(0, args.solos) if args.format == "doubles" else 0
    paired = len(emails) - invites - solos
    if paired < 0:
        print(f"--invites ({invites}) + --solos ({solos}) exceed the player count ({len(emails)}).")
        sys.exit(1)
    if paired % 2:
        # Odd player left over from pairing — make them a solo instead.
        paired -= 1
        solos += 1

    print(f"\n--- Registering {len(emails)} Players to Tournament ---")
    if args.format == "doubles":
        print(f"Plan: {paired // 2} named-partner teams, {invites} email invites, {solos} solos")
    registered = 0
    for i, email in enumerate(emails):
        payload = TournamentRegistrationPayload(tournament_id=tournament_id, email=email)
        if args.format == "doubles":
            if i < paired:
                if i % 2 == 1:
                    continue  # already claimed as a partner by emails[i - 1]
                payload.partner_email = emails[i + 1]
            elif i < paired + invites:
                payload.partner_invite_name = f"Guest {i:02d}"
                payload.partner_invite_email = f"guest{i:02d}.tourney@example.com"
            else:
                payload.needs_partner = True
        try:
            pb_tournament_service.register(tournament_id, payload, email)
            registered += 1
            print(f"Registered {email}"
                  + (f" (+ partner {payload.partner_email})" if payload.partner_email else "")
                  + (" (needs partner)" if payload.needs_partner else ""))
        except ValueError as e:
            print(f"Failed to register {email}: {e}")

    print("\n--- Generating Draw ---")
    try:
        draw_summary = pb_tournament_service.generate_draw(tournament_id)
        print(f"Draw: {draw_summary}")
    except ValueError as e:
        draw_summary = None
        print(f"Draw failed: {e}")

    final = pb_tournament_service.get_tournament_by_id(tournament_id)
    pools = final.get("pools", []) if final else []
    knockout = final.get("knockout", []) if final else []
    teams = final.get("teams", []) if final else []

    print("\n==============================================")
    print("Seed complete!")
    print(f"Tournament: {tournament.tournament_name}")
    print(f"Tournament ID: {tournament_id}")
    print(f"Club: {tournament.club_name} ({args.club})")
    print(f"Format: {args.format} | DUPR range: {args.dupr_min}-{args.dupr_max}")
    print(f"Registrations: {registered} ({args.players} players)")
    print(f"Teams: {len(teams)} | Pools: {len(pools)} | Knockout rounds: {len(knockout)}")
    print(f"Sample login: {emails[0]} / {PASSWORD}")
    print("==============================================")


if __name__ == "__main__":
    main()
