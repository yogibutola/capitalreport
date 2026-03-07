import unittest
from unittest.mock import MagicMock
from app.services.pb_league_service import PBLeagueService

class TestWithdrawalSlottingLogic(unittest.TestCase):
    def setUp(self):
        self.mock_league_store = MagicMock()
        self.service = PBLeagueService(self.mock_league_store)
        self.service.pb_match_store = MagicMock()
        self.service.generate_matches_for_group = MagicMock(return_value=[])

    def test_autoslot_excludes_withdrawn_players(self):
        """Test that withdrawn players are excluded from active_players list when slotting."""
        league_id = "l1"
        round_id = 2  # Even round ID, slotting should proceed for Play Day 1
                     # Assuming logic (round_id + 1) // 2 -> (3 // 2) = 1
                     
        group_id = 1
        
        # Withdraw player 1 for play day 1
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "rounds": [
                {
                    "round_id": 2, 
                    "group": [
                        {
                            "group_id": 1, 
                            "players": [
                                {"email": "p1@test.com"}, 
                                {"email": "p2@test.com"}, 
                                {"email": "p3@test.com"}, 
                                {"email": "p4@test.com"},
                                {"email": "p5@test.com"}
                            ]
                        }
                    ]
                }
            ],
            "withdrawals": [
                {
                    "email": "p1@test.com",
                    "play_day": 1,
                    "reason": "Sick"
                }
            ]
        }
        
        self.service.check_and_slot_next_round_group(league_id, round_id, group_id)
        
        # Verify generate_matches_for_group was called with the remaining 4 players
        self.service.generate_matches_for_group.assert_called_once()
        active_players_arg = self.service.generate_matches_for_group.call_args[0][3]
        
        # p1@test.com should be removed
        self.assertEqual(len(active_players_arg), 4)
        emails = [p["email"] for p in active_players_arg]
        self.assertNotIn("p1@test.com", emails)
        self.assertIn("p2@test.com", emails)

if __name__ == '__main__':
    unittest.main()
