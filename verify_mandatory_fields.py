from app.vo.pb.league import League
from pydantic import ValidationError
import sys

def verify_mandatory_fields():
    print("Verifying Mandatory Fields...")
    
    # helper to test field
    def test_missing_field(payload, field_name):
        try:
            League(**payload)
            print(f"❌ Failed: League created without {field_name}")
            return False
        except ValidationError as e:
            # check if the error is for the correct field
            errors = e.errors()
            if any(err['loc'][0] == field_name for err in errors):
                 print(f"✅ Success: caught missing {field_name}")
                 return True
            else:
                 print(f"❌ Failed: caught error but not for {field_name}: {e}")
                 return False

    base_payload = {
        "league_name": "Test League",
        "league_start_date": "01-01-2025",
        "group_size": 4,
        "match_format": "Singles"
    }

    # Test 1: Success with all mandatory fields
    try:
        League(**base_payload)
        print("✅ Success: League created with all mandatory fields")
    except Exception as e:
        print(f"❌ Failed: Could not create valid league: {e}")
        sys.exit(1)
        
    # Test 2: Missing league_start_date
    p = base_payload.copy()
    del p["league_start_date"]
    if not test_missing_field(p, "league_start_date"):
        sys.exit(1)
        
    # Test 3: Missing group_size
    p = base_payload.copy()
    del p["group_size"]
    if not test_missing_field(p, "group_size"):
        sys.exit(1)

    # Test 4: Missing match_format
    p = base_payload.copy()
    del p["match_format"]
    if not test_missing_field(p, "match_format"):
        sys.exit(1)

    print("\nAll verification tests passed!")

if __name__ == "__main__":
    verify_mandatory_fields()
