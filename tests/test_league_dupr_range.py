"""A league's optional DUPR band: validation on the model, gating on registration.

Both bounds are optional and a league that sets neither accepts any rating (the
behaviour every pre-existing league relies on). Once a league sets either bound,
a rating is required and must fall inside it.
"""

import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.services.pb_league_service import PBLeagueService
from app.vo.pb.league import League


def _league(**overrides):
    data = {
        "league_name": "Summer 2026",
        "league_start_date": "06-01-2026",
        "group_size": 5,
        "match_format": "round-robin",
    }
    data.update(overrides)
    return League(**data)


class TestLeagueDuprValidation(unittest.TestCase):
    def test_band_is_optional(self):
        league = _league()
        self.assertIsNone(league.dupr_min)
        self.assertIsNone(league.dupr_max)

    def test_bounds_are_kept(self):
        league = _league(dupr_min=3.0, dupr_max=4.0)
        self.assertEqual(league.dupr_min, 3.0)
        self.assertEqual(league.dupr_max, 4.0)

    def test_one_sided_band_is_allowed(self):
        self.assertEqual(_league(dupr_min=3.5).dupr_min, 3.5)
        self.assertEqual(_league(dupr_max=3.5).dupr_max, 3.5)

    def test_equal_bounds_are_allowed(self):
        league = _league(dupr_min=3.5, dupr_max=3.5)
        self.assertEqual(league.dupr_min, league.dupr_max)

    def test_inverted_range_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            _league(dupr_min=4.5, dupr_max=3.0)
        self.assertIn("dupr_max must be greater than or equal to dupr_min", str(ctx.exception))

    def test_rating_outside_zero_to_eight_is_rejected(self):
        with self.assertRaises(ValidationError):
            _league(dupr_min=-1.0)
        with self.assertRaises(ValidationError):
            _league(dupr_max=9.0)


class TestDuprErrorHelper(unittest.TestCase):
    """``_dupr_error`` returns the reason a rating is ineligible, else None."""

    def test_no_band_accepts_anything(self):
        self.assertIsNone(PBLeagueService._dupr_error(4.0, {}))
        self.assertIsNone(PBLeagueService._dupr_error(None, {}))
        self.assertIsNone(PBLeagueService._dupr_error(None, {"dupr_min": None, "dupr_max": None}))

    def test_missing_rating_is_rejected_when_a_band_exists(self):
        msg = PBLeagueService._dupr_error(None, {"dupr_min": 3.0})
        self.assertIn("required", msg)

    def test_rating_below_minimum(self):
        msg = PBLeagueService._dupr_error(2.5, {"dupr_min": 3.0, "dupr_max": 4.0})
        self.assertIn("below", msg)
        self.assertIn("3.0", msg)

    def test_rating_above_maximum(self):
        msg = PBLeagueService._dupr_error(4.5, {"dupr_min": 3.0, "dupr_max": 4.0})
        self.assertIn("above", msg)
        self.assertIn("4.0", msg)

    def test_rating_inside_band(self):
        self.assertIsNone(PBLeagueService._dupr_error(3.5, {"dupr_min": 3.0, "dupr_max": 4.0}))

    def test_bounds_are_inclusive(self):
        band = {"dupr_min": 3.0, "dupr_max": 4.0}
        self.assertIsNone(PBLeagueService._dupr_error(3.0, band))
        self.assertIsNone(PBLeagueService._dupr_error(4.0, band))

    def test_one_sided_band_only_checks_that_side(self):
        self.assertIsNone(PBLeagueService._dupr_error(8.0, {"dupr_min": 3.0}))
        self.assertIsNone(PBLeagueService._dupr_error(0.5, {"dupr_max": 4.0}))


class TestRegisterPlayerGating(unittest.TestCase):
    """``register_player`` must refuse an ineligible player before any write."""

    def setUp(self):
        self.store = MagicMock()
        # The constructor opens match and tournament stores, which demand MONGO_URI.
        with patch("app.services.pb_league_service.PBMatchStore", return_value=MagicMock()), \
                patch("app.services.pb_league_service.PBTournamentStore", return_value=MagicMock()):
            self.service = PBLeagueService(self.store)
        self.player_store = MagicMock()

    def _run(self, player_dupr, league_fields):
        """Register a player with ``player_dupr`` into a league with ``league_fields``."""
        self.player_store.find_player_by_email.return_value = {
            "firstName": "Ada",
            "lastName": "Lovelace",
            "email": "ada@test.com",
            "dupr_rating": player_dupr,
        }
        league_doc = {
            "_id": "507f1f77bcf86cd799439011",
            "league_name": "Summer 2026",
        }
        league_doc.update(league_fields)
        collection = MagicMock()
        collection.find_one.return_value = league_doc
        self.store.get_league_collection.return_value = collection

        with patch("app.services.pb_league_service.PBPlayerStore", return_value=self.player_store), \
                patch("app.services.pb_league_service.ObjectId", side_effect=lambda v: v):
            self.service.register_player("507f1f77bcf86cd799439011", "ada@test.com")

    def test_eligible_player_is_added(self):
        self._run(3.5, {"dupr_min": 3.0, "dupr_max": 4.0})
        self.store.add_player_to_league.assert_called_once()

    def test_player_below_band_is_refused_without_writing(self):
        with self.assertRaises(ValueError) as ctx:
            self._run(2.0, {"dupr_min": 3.0, "dupr_max": 4.0})
        self.assertIn("below", str(ctx.exception))
        self.store.add_player_to_league.assert_not_called()
        self.player_store.bulk_update_players_league_details.assert_not_called()

    def test_player_above_band_is_refused_without_writing(self):
        with self.assertRaises(ValueError) as ctx:
            self._run(5.0, {"dupr_min": 3.0, "dupr_max": 4.0})
        self.assertIn("above", str(ctx.exception))
        self.store.add_player_to_league.assert_not_called()

    def test_unrated_player_is_refused_by_a_banded_league(self):
        with self.assertRaises(ValueError):
            self._run(None, {"dupr_max": 4.0})
        self.store.add_player_to_league.assert_not_called()

    def test_unrated_player_joins_an_unbanded_league(self):
        self._run(None, {})
        self.store.add_player_to_league.assert_called_once()


if __name__ == "__main__":
    unittest.main()
