import unittest
from unittest.mock import MagicMock, patch
from app.services.pb_league_service import PBLeagueService

class TestPromotionRelegation(unittest.TestCase):
    def setUp(self):
        self.mock_league_store = MagicMock()
        self.service = PBLeagueService(self.mock_league_store)
        # Mock the internal match store created in __init__
        self.service.pb_match_store = MagicMock()

    def test_group_1_movements(self):
        """Test movements for the top group (Group 1)."""
        league_id = "l1"
        round_id = 1
        group_id = 1
        
        # Mock League Details with 3 groups
        self.mock_league_store.get_league_details.return_value = {
            "rounds": [
                {
                    "round_id": 1,
                    "group": [{}, {}, {}] # 3 groups
                }
            ]
        }
        
        # Mock Calculate Standings
        # Returns [Top, Middle, Middle, Bottom]
        top_player = {"email": "top@test.com"}
        mid1 = {"email": "mid1@test.com"}
        mid2 = {"email": "mid2@test.com"}
        bot_player = {"email": "bot@test.com"}
        
        self.service.calculate_group_standings = MagicMock(return_value=[
            {"player": top_player},
            {"player": mid1},
            {"player": mid2},
            {"player": bot_player}
        ])
        
        # Mock add_player_to_next_round to track calls
        self.service.add_player_to_next_round = MagicMock()
        
        self.service.process_group_promotion_relegation(league_id, round_id, group_id, [])
        
        # Verify Top Player Stays in Group 1
        self.service.add_player_to_next_round.assert_any_call(league_id, 2, 1, [top_player], "stay")
        
        # Verify Bottom Player Relegates to Group 2
        self.service.add_player_to_next_round.assert_any_call(league_id, 2, 2, [bot_player], "relegate")

    def test_last_group_movements(self):
        """Test movements for the last group (Group 3 of 3)."""
        league_id = "l1"
        round_id = 1
        group_id = 3
        
        # Mock League Details with 3 groups
        self.mock_league_store.get_league_details.return_value = {
            "rounds": [
                {
                    "round_id": 1,
                    "group": [{}, {}, {}] 
                }
            ]
        }
        
        top_player = {"email": "top@test.com"}
        bot_player = {"email": "bot@test.com"}
        
        self.service.calculate_group_standings = MagicMock(return_value=[
            {"player": top_player},
            {"player": {}, "email": "m1"},
            {"player": {}, "email": "m2"},
            {"player": bot_player}
        ])
        
        self.service.add_player_to_next_round = MagicMock()
        
        self.service.process_group_promotion_relegation(league_id, round_id, group_id, [])
        
        # Verify Top Player Promotes to Group 2
        self.service.add_player_to_next_round.assert_any_call(league_id, 2, 2, [top_player], "promote")
        
        # Verify Bottom Player Stays in Group 3 (Last Group)
        self.service.add_player_to_next_round.assert_any_call(league_id, 2, 3, [bot_player], "stay")

if __name__ == '__main__':
    unittest.main()
