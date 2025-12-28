from app.vo.pb.league import League
from pydantic import ValidationError
import sys

def verify_league_name_mandatory():
    print("Verifying League Name Mandatory...")
    
    # Test case 1: Missing league_name
    try:
        League(league_id="123")
        print("❌ Failed: League created without league_name")
        sys.exit(1)
    except ValidationError as e:
        print("✅ Success: caught missing league_name error")
        
    # Test case 2: Valid league_name
    try:
        league = League(league_name="My Valid League")
        print(f"✅ Success: League created with name: {league.league_name}")
    except Exception as e:
        print(f"❌ Failed: Could not create league with valid name: {e}")
        sys.exit(1)

    print("\nAll verification tests passed!")

if __name__ == "__main__":
    verify_league_name_mandatory()
