import sys
import os

# Add the parent directory to sys.path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.services.pb_league_service import PBLeagueService
from app.vo.pb.league import League
from bson import ObjectId

def verify_registration():
    league_store = PBLeagueStore()
    player_store = PBPlayerStore()
    service = PBLeagueService(league_store)

    email = "test_player_reg@example.com"
    league_name = "Test Registration League"

    # 1. Cleanup old data
    player_store.get_players_collection().delete_one({"email": email})
    league_store.get_league_collection().delete_one({"league_name": league_name})

    # 2. Create test player
    player_data = {
        "firstName": "Test",
        "lastName": "Player",
        "email": email,
        "dupr_rating": 4.5,
        "leagues": []
    }
    player_store.create_player(player_data)
    print(f"Created test player: {email}")

    # 3. Create test league
    league = League(
        league_name=league_name,
        league_description="Testing registration",
        league_start_date="01-01-2026",
        group_size=4,
        match_format="Best of 3"
    )
    league_store.store_new_league_details(league)
    
    # Re-fetch to get the assigned _id
    league_doc = league_store.get_league_collection().find_one({"league_name": league_name})
    league_id = str(league_doc["_id"])
    print(f"Created test league: {league_name} with ID: {league_id}")

    # 4. Register player
    print("Registering player...")
    service.register_player(league_id, email)

    # 5. Verify league document
    updated_league = league_store.get_league_collection().find_one({"_id": ObjectId(league_id)})
    player_emails_in_league = [p["email"] for p in updated_league.get("players", [])]
    if email in player_emails_in_league:
        print("SUCCESS: Player found in league document")
    else:
        print("FAILURE: Player NOT found in league document")

    # 6. Verify player document
    updated_player = player_store.find_player_by_email(email)
    league_ids_in_player = [l["league_id"] for l in updated_player.get("leagues", [])]
    if league_id in league_ids_in_player:
        print("SUCCESS: League found in player document")
    else:
        print("FAILURE: League NOT found in player document")

if __name__ == "__main__":
    try:
        verify_registration()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
