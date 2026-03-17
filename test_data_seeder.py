import argparse
import sys
from datetime import datetime
from fastapi import HTTPException

from app.store.mongo.pb_league_store import PBLeagueStore
from app.services.pb_league_service import PBLeagueService
from app.store.mongo.pb_player_store import PBPlayerStore
from app.services.pb_player_service import PBPlayerService
from app.vo.pb.league import League
from app.vo.pb.player import PlayerSignup

def main():
    parser = argparse.ArgumentParser(description="Seed test league and test players.")
    parser.add_argument("--players", type=int, default=9, help="Number of test players to create and add to the league")
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
        
        signup_data = PlayerSignup(
            firstName=first_name,
            lastName=last_name,
            email=email,
            password=password,
            dupr_rating=3.0 + (i * 0.1)  # slightly varied DUPR rating
        )

        try:
            pb_player_service.register_player(signup_data)
            print(f"Created player: {email} / Password: {password}")
        except HTTPException as e:
            if e.status_code == 409:
                print(f"Player already exists: {email}. Will use existing player.")
            else:
                print(f"Error creating player {email}: {e.detail}")
                sys.exit(1)
        
        registered_emails.append(email)

    print("\n--- Creating League ---")
    today = datetime.now().strftime("%m-%d-%Y")
    league = League(
        league_name=f"Pro_{timestamp}",
        league_description="League created by seed script for testing.",
        league_start_date=today,
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
