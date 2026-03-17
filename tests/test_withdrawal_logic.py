import unittest
from unittest.mock import MagicMock, patch
from app.services.pb_league_service import PBLeagueService

class TestWithdrawalSlottingLogic(unittest.TestCase):
    @patch('app.services.pb_league_service.PBMatchStore')
    def setUp(self, mock_match_store_class):
        self.mock_league_store = MagicMock()
        self.service = PBLeagueService(self.mock_league_store)
        self.service.pb_match_store = mock_match_store_class.return_value
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

    def test_slot_first_round_of_day(self):
        """Test slot_first_round_of_day groups players correctly by sorting their dupr rating and excluding withdrawals."""
        league_id = "l1"
        play_day = 1 # Translates to round 1
                     
        # Mocking data to be returned
        league_data = {
            "group_size": 4,
            "players": [
                {"email": "p1@test.com", "dupr_rating": "5.0"}, 
                {"email": "p2@test.com", "dupr_rating": "4.1"}, 
                {"email": "p3@test.com", "dupr_rating": "3.5"}, 
                {"email": "p4@test.com", "dupr_rating": "4.5"},
                {"email": "p5@test.com", "dupr_rating": "4.0"} # This player should be withdrawn from logic
            ],
            "withdrawals": [
                {
                    "email": "p5@test.com",
                    "play_day": 1,
                    "reason": "Out of town"
                }
            ],
            "rounds": []
        }
        self.mock_league_store.get_league_details.return_value = league_data
        
        # Simulate add_players_to_round_group modifying the database
        def mock_add_players(l_id, r_id, g_id, players):
            league_data["rounds"] = [{
                "round_id": r_id,
                "group": [{
                    "group_id": g_id,
                    "players": players
                }]
            }]
            
        self.mock_league_store.add_players_to_round_group.side_effect = mock_add_players
        
        self.service.slot_first_round_of_day(league_id, play_day)
        
        # Verify generate_matches_for_group called with right group properties
        self.service.generate_matches_for_group.assert_called_once()
        
        # Checking add_players_to_round_group directly
        self.mock_league_store.add_players_to_round_group.assert_called_once()
        active_players_added = self.mock_league_store.add_players_to_round_group.call_args[0][3]
        
        # Verify length of 4 since p5 is withdrawn
        self.assertEqual(len(active_players_added), 4)
        
        emails_ordered = [p["email"] for p in active_players_added]
        # Needs to be ordered by dupr_rating desc: p1, p4, p2, p3
        self.assertEqual(emails_ordered, ["p1@test.com", "p4@test.com", "p2@test.com", "p3@test.com"])

if __name__ == '__main__':
    unittest.main()

