import argparse
import sys
from datetime import datetime
from fastapi import HTTPException

from app.store.mongo.pb_league_store import PBLeagueStore
from app.services.pb_league_service import PBLeagueService
from app.services.pb_club_service import PBClubService
from app.store.mongo.pb_club_store import PBClubStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.services.pb_player_service import PBPlayerService
from app.vo.pb.league import League
from app.vo.pb.player import PlayerSignup

# (city, state, zip) assigned round-robin to the seeded players, ordered roughly
# nearest-to-farthest from the first entry, so a distance search has players both
# inside and outside a radius. Approx miles from Ashburn (20147):
#   Ashburn 0, Sterling 4, Herndon 8, Leesburg 8, Reston 11,
#   Centreville 17, Fairfax 20, Alexandria 30, Baltimore 60.
PLAYER_ZIPS = [
    ("Ashburn", "VA", "20147"),
    ("Sterling", "VA", "20164"),
    ("Herndon", "VA", "20170"),
    ("Leesburg", "VA", "20176"),
    ("Reston", "VA", "20191"),
    ("Centreville", "VA", "20121"),
    ("Fairfax", "VA", "22030"),
    ("Alexandria", "VA", "22314"),
    ("Baltimore", "MD", "21201"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed test league and test players.")
    parser.add_argument("--players", type=int, default=9, help="Number of test players to create and add to the league")
    parser.add_argument(
        "--club",
        default="test_pro@gmail.com",
        help="Email of the organiser whose club owns the league; /api/v1/my_leagues lists that club's leagues. "
             "Defaults to the account the Playwright e2e specs sign in with.",
    )
    args = parser.parse_args()

    players = [
        {"first": "Dhirender", "last": "B"},
        {"first": "Usha",      "last": "B"},
        {"first": "Aditya",    "last": "Butola"},
        {"first": "Shreya",    "last": "Butola"},
        {"first": "Animesh",   "last": "Butola"},
        {"first": "Santoshi",  "last": "Butola"},
        {"first": "Samar",     "last": "Butola"},
        {"first": "Deepak",    "last": "Panwar"},
        {"first": "Pratibha",  "last": "Panwar"},
        # {"first": "Vivaan",    "last": "Panwar"},
        # {"first": "Kaira",     "last": "Panwar"},
        # {"first": "Dave",      "last": "Lefevre"},
        # {"first": "Dan",       "last": "Lefevre"},
        # {"first": "Susan",     "last": "Lefevre"}
    ]
    num_players = len(players)
    print(f"Starting seed process with {num_players} players...")

    # Initialize stores and services
    pb_league_store = PBLeagueStore()
    pb_league_service = PBLeagueService(pb_league_store)
    pb_player_store = PBPlayerStore()
    pb_player_service = PBPlayerService(pb_player_store)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = "Password@123"

    print("--- Creating/Verifying Players ---")
    registered_emails = []
    for i, p in enumerate(players, start=1):
        first_name = p["first"]
        last_name = p["last"]
        email = f"{first_name.lower()}.{last_name.lower()}@test.com"
        # Spread across Northern Virginia so a radius search has players both
        # inside and outside any given distance. PLAYER_ZIPS is ordered
        # nearest-to-farthest from the first entry.
        city, state, zip_code = PLAYER_ZIPS[(i - 1) % len(PLAYER_ZIPS)]

        signup_data = PlayerSignup(
            firstName=first_name,
            lastName=last_name,
            email=email,
            password=password,
            dupr_rating=3.0 + (i * 0.1),  # slightly varied DUPR rating
            city=city,
            state=state,
            zip_code=zip_code,
        )

        try:
            pb_player_service.register_player(signup_data)
            print(f"Created player: {email} / Password: {password} / {city} {zip_code}")
        except HTTPException as e:
            if e.status_code == 409:
                print(f"Player already exists: {email}. Will use existing player.")
            else:
                print(f"Error creating player {email}: {e.detail}")
                sys.exit(1)

        # Outside the try/except so re-running the seeder backfills location onto
        # players created before this field existed.
        pb_player_store.update_player_profile(
            email, {"city": city, "state": state, "zip_code": zip_code})

        registered_emails.append(email)

    club = PBClubService(PBClubStore(), PBPlayerStore()).club_for_owner_email(args.club)
    if not club:
        print(f"No club is run by '{args.club}'. Sign up a club with that email first, or pass --club.")
        sys.exit(1)

    print("\n--- Creating League ---")
    today = datetime.now().strftime("%m-%d-%Y")
    league = League(
        club_id=str(club["_id"]),
        league_name=f"Pro_{timestamp}",
        league_description="League created by seed script for testing.",
        league_start_date=today,
        league_duration="10",   
        group_size=4,
        match_format="Doubles",
        league_status="Active"
    )

    pb_league_service.save_league_details(league)
    league_id = str(league.league_id)
    print(f"Created League ID: {league_id} | Name: {league.league_name}")

    print("\n--- Registering Players to League ---")
    for email in registered_emails:
        try:
            pb_league_service.register_player(league_id, email)
            print(f"Registered {email} to league {league_id}")
        except ValueError as e:
            print(f"Failed to register {email}: {e}")

    print("\n==============================================")
    print(f"Seed complete!")
    print(f"League Name: {league.league_name}")
    print(f"Number of players: {num_players}")
    first = players[0]
    sample_email = f"{first['first'].lower()}.{first['last'].lower()}@test.com"
    print(f"Sample Login: {sample_email} / {password}")
    print("==============================================")


if __name__ == "__main__":
    main()
