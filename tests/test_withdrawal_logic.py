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

    def test_promotion_relegation_does_not_autoslot_first_round_of_day2(self):
        """
        When round 2 (last round of day 1) completes and promotion/relegation
        populates round 3 (first round of day 2), NO matches should be
        auto-generated. Round 3 is odd → the autoslot guard must block it.
        Groups should be populated but have zero matches.
        """
        league_id = "l1"

        all_players = [
            {"email": f"p{i}@test.com", "dupr_rating": str(5.0 - i * 0.2)}
            for i in range(1, 10)
        ]
        withdrawn_email = "p5@test.com"

        # Day 1 round 2 just finished. Groups for round 2 have been populated.
        league_data = {
            "group_size": 4,
            "players": all_players,
            "withdrawals": [
                {"email": withdrawn_email, "play_day": 2, "reason": "Injury"}
            ],
            "rounds": [
                {
                    "round_id": 2,
                    "group": [
                        {
                            "group_id": 1,
                            "group_size": 5,
                            "players": all_players[0:5],
                        },
                        {
                            "group_id": 2,
                            "group_size": 4,
                            "players": all_players[5:9],
                        }
                    ]
                }
            ]
        }
        self.mock_league_store.get_league_details.return_value = league_data

        # check_and_slot_next_round_group is called by promotion/relegation
        # with round_id=3 (odd). It should bail out immediately.
        self.service.check_and_slot_next_round_group(league_id, round_id=3, group_id=1)
        self.service.check_and_slot_next_round_group(league_id, round_id=3, group_id=2)

        # No matches should be generated for any group in round 3
        self.service.generate_matches_for_group.assert_not_called()
        self.service.pb_match_store.store_match_details.assert_not_called()
        self.mock_league_store.set_group_matches.assert_not_called()

    def test_nine_players_one_withdrawal_day2_manual_slot_produces_two_groups_of_four(self):
        """
        9-player league: one player withdraws from day 2.
        Round 3 (first round of day 2) has groups pre-populated by
        promotion/relegation but NO matches yet.
        When admin manually calls slot_first_round_of_day, it should:
          - exclude the withdrawn player
          - produce 2 groups with 4 active players each
          - generate matches for both groups
        """
        league_id = "l1"
        play_day = 2  # round_id = play_day * 2 - 1 = 3

        all_players = [
            {"email": f"p{i}@test.com", "dupr_rating": str(5.0 - i * 0.2)}
            for i in range(1, 10)
        ]
        # p5 withdraws from day 2
        withdrawn_email = "p5@test.com"

        # Pre-existing groups in round 3 from day 1 promotion/relegation
        # (groups populated, but NO matches — first round of day is never auto-slotted)
        league_data = {
            "group_size": 4,
            "players": all_players,
            "withdrawals": [
                {"email": withdrawn_email, "play_day": 2, "reason": "Injury"}
            ],
            "rounds": [
                {
                    "round_id": 3,
                    "group": [
                        {
                            "group_id": 1,
                            "players": [
                                all_players[0],  # p1
                                all_players[1],  # p2
                                all_players[2],  # p3
                                all_players[3],  # p4
                                all_players[4],  # p5 (will be withdrawn)
                            ]
                        },
                        {
                            "group_id": 2,
                            "players": [
                                all_players[5],  # p6
                                all_players[6],  # p7
                                all_players[7],  # p8
                                all_players[8],  # p9
                            ]
                        }
                    ]
                }
            ]
        }
        self.mock_league_store.get_league_details.return_value = league_data

        # Track group player updates
        updated_groups = {}

        def mock_update_players(l_id, r_id, g_id, players):
            # Simulate the store updating the group's players in league_data
            for rnd in league_data["rounds"]:
                if int(rnd["round_id"]) == r_id:
                    for grp in rnd["group"]:
                        if int(grp["group_id"]) == g_id:
                            grp["players"] = players
            updated_groups[g_id] = players

        self.mock_league_store.update_round_group_players.side_effect = mock_update_players

        # Admin manually triggers slotting for day 2
        self.service.slot_first_round_of_day(league_id, play_day)

        # --- Assertions ---

        # generate_matches_for_group should have been called for each group
        self.assertEqual(self.service.generate_matches_for_group.call_count, 2)

        # Collect all players passed to generate_matches_for_group across both calls
        all_slotted_players = []
        for call in self.service.generate_matches_for_group.call_args_list:
            players_arg = call[0][3]
            all_slotted_players.append(players_arg)

        # Each group should have exactly 4 players
        for idx, group_players in enumerate(all_slotted_players):
            self.assertEqual(
                len(group_players), 4,
                f"Group {idx + 1} should have 4 players but has {len(group_players)}"
            )

        # Total active players across both groups should be 8
        total_players = sum(len(gp) for gp in all_slotted_players)
        self.assertEqual(total_players, 8)

        # The withdrawn player must NOT appear in any group
        all_emails = [p["email"] for gp in all_slotted_players for p in gp]
        self.assertNotIn(withdrawn_email, all_emails,
                         f"Withdrawn player {withdrawn_email} should not be in any group")

        # Verify update_round_group_players was called for group 1 (which had the withdrawn player)
        self.mock_league_store.update_round_group_players.assert_called()
        # Group 1 should have been updated to remove the withdrawn player
        self.assertIn(1, updated_groups)
        group1_emails = [p["email"] for p in updated_groups[1]]
        self.assertNotIn(withdrawn_email, group1_emails)
        self.assertEqual(len(updated_groups[1]), 4)


if __name__ == '__main__':
    unittest.main()

