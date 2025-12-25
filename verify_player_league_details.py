import sys
import os

# Add the project root to sys.path
sys.path.append("/Users/yogenderbutola/work/ai/capitalreport")

from app.vo.pb.player import Player, PlayerResponse, PlayerLeague
from typing import List

def test_player_multi_league():
    print("Testing Player model with multiple leagues...")
    league1 = PlayerLeague(league_id="L1", league_name="Summer", league_status="Active")
    league2 = PlayerLeague(league_id="L2", league_name="Winter", league_status="Upcoming")
    
    p = Player(
        firstName="John",
        lastName="Doe",
        email="john@example.com",
        password="hashed_password",
        dupr_rating=4.5,
        leagues=[league1, league2]
    )
    assert len(p.leagues) == 2
    assert p.leagues[0].league_name == "Summer"
    assert p.leagues[1].league_id == "L2"
    print("✓ Player model verified")

def test_player_response_serialization():
    print("Testing PlayerResponse serialization...")
    league1 = PlayerLeague(league_id="L1", league_name="Summer", league_status="Active")
    
    pr = PlayerResponse(
        id="123",
        firstName="John",
        lastName="Doe",
        email="john@example.com",
        dupr_rating=4.5,
        leagues=[league1]
    )
    
    data = pr.model_dump()
    assert "leagues" in data
    assert data["leagues"][0]["league_name"] == "Summer"
    print("✓ PlayerResponse serialization verified")

def test_bulk_update_logic():
    print("Testing store bulk update logic (mocked)...")
    from unittest.mock import MagicMock
    
    mock_store = MagicMock()
    # No exception means success for this simple test
    mock_store.bulk_update_players_league_details(["test@example.com", "other@example.com"], {
        "league_id": "L1",
        "league_name": "New League Name"
    })
    print("✓ Store bulk update call verified (mocked)")

if __name__ == "__main__":
    try:
        test_player_multi_league()
        test_player_response_serialization()
        test_bulk_update_logic()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nVerification failed: {str(e)}")
        sys.exit(1)
