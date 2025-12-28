from app.vo.pb.league import League
import sys

def verify_league_fix():
    print("Verifying League model fix...")
    
    # Test case 1: league_id is 0
    try:
        league = League(league_id=0)
        if league.league_id is None:
            print("✅ Success: league_id=0 converted to None")
        else:
            print(f"❌ Failed: league_id=0 became {league.league_id}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed: Exception raised for league_id=0: {e}")
        sys.exit(1)

    # Test case 2: league_id is allowed string
    try:
        test_id = "test_id_123"
        league = League(league_id=test_id)
        if league.league_id == test_id:
             print(f"✅ Success: league_id='{test_id}' preserved")
        else:
            print(f"❌ Failed: league_id='{test_id}' became {league.league_id}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed: Exception raised for league_id='{test_id}': {e}")
        sys.exit(1)
        
    # Test case 3: league_id is None
    try:
        league = League(league_id=None)
        if league.league_id is None:
             print("✅ Success: league_id=None preserved")
        else:
            print(f"❌ Failed: league_id=None became {league.league_id}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed: Exception raised for league_id=None: {e}")
        sys.exit(1)

    print("\nAll verification tests passed!")

if __name__ == "__main__":
    verify_league_fix()
