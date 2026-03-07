import unittest
from unittest.mock import MagicMock
from app.services.pb_league_service import PBLeagueService

class TestAutoslotLogic(unittest.TestCase):
    def setUp(self):
        self.mock_league_store = MagicMock()
        self.service = PBLeagueService(self.mock_league_store)
        self.service.pb_match_store = MagicMock()
        self.service.generate_matches_for_group = MagicMock(return_value=[])

    def test_autoslot_even_round(self):
        """Test that autoslot proceeds when round_id is even."""
        league_id = "l1"
        round_id = 2  # Even round ID, slotting should proceed
        group_id = 1
        
        # Mock dependencies to reach the slotting logic
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "rounds": [{"round_id": 2, "group": [{"group_id": 1, "players": [1, 2, 3, 4]}]}]
        }
        
        self.service.check_and_slot_next_round_group(league_id, round_id, group_id)
        
        self.service.generate_matches_for_group.assert_called_once()
        self.service.pb_match_store.store_match_details.assert_called_once()
        self.service.pb_league_store.set_group_matches.assert_called_once()

    def test_no_autoslot_odd_round(self):
        """Test that autoslot is bypassed when round_id is odd."""
        league_id = "l1"
        round_id = 1  # Odd round ID, slotting should return early
        group_id = 1
        
        # This shouldn't be reached, but we can mock it anyway
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "rounds": [{"round_id": 1, "group": [{"group_id": 1, "players": [1, 2, 3, 4]}]}]
        }
        
        self.service.check_and_slot_next_round_group(league_id, round_id, group_id)
        
        self.service.generate_matches_for_group.assert_not_called()
        self.service.pb_match_store.store_match_details.assert_not_called()
        self.service.pb_league_store.set_group_matches.assert_not_called()

if __name__ == '__main__':
    unittest.main()
