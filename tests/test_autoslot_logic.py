import unittest
from unittest.mock import MagicMock, call, patch
from app.services.pb_league_service import PBLeagueService


def make_completed_matches(n=3):
    return [{"match_status": "completed"} for _ in range(n)]


def make_incomplete_matches(n=3):
    matches = make_completed_matches(n)
    matches[0]["match_status"] = "YetToPlay"
    return matches


def league_doc_with_prev_round(prev_round_groups: dict, group_size: int = 4) -> dict:
    """
    Build a league doc that has:
      - An even round (round_id=2) with one group containing enough players.
      - A previous round (round_id=1) with groups as specified in prev_round_groups.
    prev_round_groups: {group_id: [player_list]}
    """
    players_4 = [{"email": f"{i}@e.com"} for i in range(1, 5)]
    even_round = {
        "round_id": 2,
        "group": [{"group_id": 1, "players": players_4, "match": []}],
    }
    odd_round_groups = [
        {"group_id": gid, "players": plist, "match": []}
        for gid, plist in prev_round_groups.items()
    ]
    return {
        "group_size": group_size,
        "withdrawals": [],
        "rounds": [{"round_id": 1, "group": odd_round_groups}, even_round],
    }


class TestAutoslotLogic(unittest.TestCase):
    def setUp(self):
        self.mock_league_store = MagicMock()
        self.service = PBLeagueService(self.mock_league_store)
        self.service.pb_match_store = MagicMock()
        self.service.generate_matches_for_group = MagicMock(return_value=[])

    # -----------------------------------------------------------------------
    # Existing tests (updated to mock prev-round match data)
    # -----------------------------------------------------------------------

    def test_autoslot_even_round(self):
        """Autoslot proceeds when round_id is even AND adjacent matches are complete."""
        league_id = "l1"
        round_id = 2
        group_id = 1

        # League has 1 group in prev round (round 1) — first group, so no prev neighbour needed
        self.mock_league_store.get_league_details.return_value = league_doc_with_prev_round(
            {1: [{"email": "a@e.com"}]}, group_size=4
        )
        # Return completed matches for prev round (round 1), empty for target round (round 2)
        def match_side_effect(lid, rid, gid):
            if rid == 1:
                return make_completed_matches()
            return []  # No existing matches for round 2 yet
        self.service.pb_match_store.get_matches_by_group.side_effect = match_side_effect

        self.service.check_and_slot_next_round_group(league_id, round_id, group_id)

        self.service.generate_matches_for_group.assert_called_once()
        self.service.pb_match_store.store_match_details.assert_called_once()
        self.service.pb_league_store.set_group_matches.assert_called_once()

    def test_no_autoslot_odd_round(self):
        """Autoslot is bypassed when round_id is odd (1st round of the day)."""
        self.service.check_and_slot_next_round_group("l1", 1, 1)

        self.service.generate_matches_for_group.assert_not_called()
        self.service.pb_match_store.store_match_details.assert_not_called()
        self.service.pb_league_store.set_group_matches.assert_not_called()

    # -----------------------------------------------------------------------
    # New tests — Rules 1-3: adjacent group completion
    # -----------------------------------------------------------------------

    def test_no_autoslot_adjacent_not_complete(self):
        """Middle group should NOT slot if an adjacent group still has incomplete matches."""
        # 3 groups in prev round; current is group 2 (middle)
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "withdrawals": [],
            "rounds": [
                {
                    "round_id": 1,
                    "group": [
                        {"group_id": 1, "players": []},
                        {"group_id": 2, "players": []},
                        {"group_id": 3, "players": []},
                    ],
                },
                {
                    "round_id": 2,
                    "group": [
                        {
                            "group_id": 2,
                            "players": [{"email": f"{i}@e.com"} for i in range(1, 5)],
                            "match": [],
                        }
                    ],
                },
            ],
        }

        def side_effect(league_id, round_id, gid):
            # For target round (2): no existing matches
            if round_id == 2:
                return []
            # For prev round (1): Group 1 is incomplete; groups 2, 3 are complete
            if gid == 1:
                return make_incomplete_matches()
            return make_completed_matches()

        self.service.pb_match_store.get_matches_by_group.side_effect = side_effect

        self.service.check_and_slot_next_round_group("l1", 2, 2)

        self.service.generate_matches_for_group.assert_not_called()

    def test_autoslot_first_group_only_next_required(self):
        """First group only needs the NEXT group's matches to be complete."""
        # 2 groups in prev round; current is group 1 (first), so only group 2 matters
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "withdrawals": [],
            "rounds": [
                {
                    "round_id": 1,
                    "group": [
                        {"group_id": 1, "players": []},
                        {"group_id": 2, "players": []},
                    ],
                },
                {
                    "round_id": 2,
                    "group": [
                        {
                            "group_id": 1,
                            "players": [{"email": f"{i}@e.com"} for i in range(1, 5)],
                            "match": [],
                        }
                    ],
                },
            ],
        }
        # Return completed for prev round (1), empty for target round (2)
        def match_side_effect(lid, rid, gid):
            if rid == 1:
                return make_completed_matches()
            return []
        self.service.pb_match_store.get_matches_by_group.side_effect = match_side_effect

        self.service.check_and_slot_next_round_group("l1", 2, 1)

        self.service.generate_matches_for_group.assert_called_once()

    def test_autoslot_last_group_only_prev_required(self):
        """Last group only needs the PREVIOUS group's matches to be complete."""
        # 2 groups in prev round; current is group 2 (last)
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "withdrawals": [],
            "rounds": [
                {
                    "round_id": 1,
                    "group": [
                        {"group_id": 1, "players": []},
                        {"group_id": 2, "players": []},
                    ],
                },
                {
                    "round_id": 2,
                    "group": [
                        {
                            "group_id": 2,
                            "players": [{"email": f"{i}@e.com"} for i in range(1, 5)],
                            "match": [],
                        }
                    ],
                },
            ],
        }
        # Return completed for prev round (1), empty for target round (2)
        def match_side_effect(lid, rid, gid):
            if rid == 1:
                return make_completed_matches()
            return []
        self.service.pb_match_store.get_matches_by_group.side_effect = match_side_effect

        self.service.check_and_slot_next_round_group("l1", 2, 2)

        self.service.generate_matches_for_group.assert_called_once()

    def test_autoslot_middle_all_adjacent_complete(self):
        """Middle group slots when BOTH adjacent groups are fully complete."""
        self.mock_league_store.get_league_details.return_value = {
            "group_size": 4,
            "withdrawals": [],
            "rounds": [
                {
                    "round_id": 1,
                    "group": [
                        {"group_id": 1, "players": []},
                        {"group_id": 2, "players": []},
                        {"group_id": 3, "players": []},
                    ],
                },
                {
                    "round_id": 2,
                    "group": [
                        {
                            "group_id": 2,
                            "players": [{"email": f"{i}@e.com"} for i in range(1, 5)],
                            "match": [],
                        }
                    ],
                },
            ],
        }
        # Return completed for prev round (1), empty for target round (2)
        def match_side_effect(lid, rid, gid):
            if rid == 1:
                return make_completed_matches()
            return []
        self.service.pb_match_store.get_matches_by_group.side_effect = match_side_effect

        self.service.check_and_slot_next_round_group("l1", 2, 2)

        self.service.generate_matches_for_group.assert_called_once()

    # -----------------------------------------------------------------------
    # New tests — Rule 5: player positioning on promotion / relegation
    # -----------------------------------------------------------------------

    def test_promoted_player_is_bottom_of_new_group(self):
        """Top player moving to an upper group is appended (becomes bottom seed)."""
        self.mock_league_store.add_players_to_round_group = MagicMock()
        self.service.check_and_slot_next_round_group = MagicMock()

        top_player = {"email": "top@e.com"}

        # Simulate: current group 2 of 3, top player goes to group 1
        self.service.add_player_to_next_round("l1", 2, 1, [top_player], "promote", position="append")

        self.mock_league_store.add_players_to_round_group.assert_called_once_with(
            "l1", 2, 1, [top_player], position="append"
        )

    def test_relegated_player_is_top_of_new_group(self):
        """Bottom player moving to a lower group is prepended (becomes top seed)."""
        self.mock_league_store.add_players_to_round_group = MagicMock()
        self.service.check_and_slot_next_round_group = MagicMock()

        bottom_player = {"email": "bottom@e.com"}

        # Simulate: current group 1 of 3, bottom player goes to group 2
        self.service.add_player_to_next_round("l1", 2, 2, [bottom_player], "relegate", position="prepend")

        self.mock_league_store.add_players_to_round_group.assert_called_once_with(
            "l1", 2, 2, [bottom_player], position="prepend"
        )


if __name__ == "__main__":
    unittest.main()
