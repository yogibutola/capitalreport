"""Age divisions and the mixed-doubles match format.

Age groups are labels only — they are stored and displayed but never gate
registration. The mixed-doubles tests are the regression guard: every code path
that used to compare ``match_format == "doubles"`` must now treat mixed doubles
as a partner format too.
"""

import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.services.pb_tournament_service import PBTournamentService
from app.vo.pb.tournament import Tournament, is_doubles_format
from app.vo.pb.tournament_registration_payload import TournamentRegistrationPayload


def _fixture(**overrides):
    data = {
        "tournament_name": "Fall Open",
        "tournament_start_date": "10-01-2026",
    }
    data.update(overrides)
    return Tournament(**data)


def _doc(**overrides):
    doc = {
        "tournament_id": "T1",
        "tournament_name": "Fall Open",
        "tournament_status": "pending",
        "match_format": "mixed-doubles",
        "registrations": [],
    }
    doc.update(overrides)
    return doc


class TestAgeGroupNormalization(unittest.TestCase):
    def test_open_clears_any_supplied_bounds(self):
        t = _fixture(age_group="open", age_min=30, age_max=45)
        self.assertIsNone(t.age_min)
        self.assertIsNone(t.age_max)

    def test_default_is_open(self):
        t = _fixture()
        self.assertEqual(t.age_group, "open")
        self.assertIsNone(t.age_min)

    def test_preset_derives_lower_bound(self):
        t = _fixture(age_group="50+")
        self.assertEqual(t.age_min, 50)
        self.assertIsNone(t.age_max)

    def test_preset_overrides_supplied_bounds(self):
        t = _fixture(age_group="35+", age_min=12, age_max=99)
        self.assertEqual(t.age_min, 35)
        self.assertIsNone(t.age_max)

    def test_custom_requires_at_least_one_bound(self):
        with self.assertRaises(ValidationError) as ctx:
            _fixture(age_group="custom")
        self.assertIn("minimum or maximum age", str(ctx.exception))

    def test_custom_rejects_inverted_range(self):
        with self.assertRaises(ValidationError) as ctx:
            _fixture(age_group="custom", age_min=45, age_max=30)
        self.assertIn("age_max must be greater than or equal to age_min", str(ctx.exception))

    def test_custom_accepts_one_bound(self):
        self.assertEqual(_fixture(age_group="custom", age_min=30).age_min, 30)
        self.assertEqual(_fixture(age_group="custom", age_max=45).age_max, 45)

    def test_custom_keeps_both_bounds(self):
        t = _fixture(age_group="custom", age_min=30, age_max=45)
        self.assertEqual((t.age_min, t.age_max), (30, 45))

    def test_unknown_age_group_is_rejected(self):
        with self.assertRaises(ValidationError):
            _fixture(age_group="masters")

    def test_bounds_outside_range_are_rejected(self):
        with self.assertRaises(ValidationError):
            _fixture(age_group="custom", age_min=4)
        with self.assertRaises(ValidationError):
            _fixture(age_group="custom", age_max=121)


class TestAgeGroupLabel(unittest.TestCase):
    def test_open(self):
        self.assertEqual(_fixture().age_group_label, "Open")

    def test_preset(self):
        self.assertEqual(_fixture(age_group="60+").age_group_label, "60+")

    def test_custom_both_bounds(self):
        t = _fixture(age_group="custom", age_min=30, age_max=45)
        self.assertEqual(t.age_group_label, "30–45")

    def test_custom_min_only(self):
        self.assertEqual(_fixture(age_group="custom", age_min=30).age_group_label, "30+")

    def test_custom_max_only(self):
        self.assertEqual(_fixture(age_group="custom", age_max=45).age_group_label, "Up to 45")


class TestMatchFormat(unittest.TestCase):
    def test_mixed_doubles_is_accepted(self):
        self.assertEqual(_fixture(match_format="mixed-doubles").match_format, "mixed-doubles")

    def test_default_is_doubles(self):
        self.assertEqual(_fixture().match_format, "doubles")

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValidationError):
            _fixture(match_format="triples")

    def test_is_doubles_format(self):
        for fmt in ("doubles", "mixed-doubles", None, ""):
            self.assertTrue(is_doubles_format(fmt), fmt)
        self.assertFalse(is_doubles_format("singles"))


class TestMixedDoublesBehavesLikeDoubles(unittest.TestCase):
    """Mixed doubles must ride the doubles paths: partners and team seeding."""

    def setUp(self):
        self.tournament_store = MagicMock()
        self.service = PBTournamentService(self.tournament_store)

        self._players = {
            "ann@example.com": {
                "firstName": "Ann",
                "lastName": "Lee",
                "email": "ann@example.com",
                "dupr_rating": 4.0,
            },
            "bob@example.com": {
                "firstName": "Bob",
                "lastName": "Ray",
                "email": "bob@example.com",
                "dupr_rating": 3.8,
            },
        }
        self.player_store = MagicMock()
        self.player_store.find_player_by_email.side_effect = lambda e: self._players.get(
            (e or "").lower()
        )

        patcher = patch(
            "app.services.pb_tournament_service.PBPlayerStore",
            return_value=self.player_store,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_register_records_the_named_partner(self):
        self.tournament_store.get_tournament_details.return_value = _doc()

        self.service.register(
            "T1",
            TournamentRegistrationPayload(tournament_id="T1", partner_email="bob@example.com"),
            "ann@example.com",
        )

        saved = self.tournament_store.update_tournament.call_args[0][1]
        self.assertEqual(len(saved["registrations"]), 1)
        self.assertEqual(saved["registrations"][0]["partner_email"], "bob@example.com")

    def test_register_flags_looking_for_a_partner(self):
        self.tournament_store.get_tournament_details.return_value = _doc()

        self.service.register(
            "T1",
            TournamentRegistrationPayload(tournament_id="T1", needs_partner=True),
            "ann@example.com",
        )

        saved = self.tournament_store.update_tournament.call_args[0][1]
        self.assertTrue(saved["registrations"][0]["needs_partner"])

    def test_generate_draw_builds_teams_and_reports_the_format(self):
        self.tournament_store.get_tournament_details.return_value = _doc(
            pool_size=4,
            advancers_per_pool=2,
            registrations=[
                {
                    "firstName": "Ann",
                    "lastName": "Lee",
                    "email": "ann@example.com",
                    "dupr_rating": 4.0,
                    "partner_email": "bob@example.com",
                    "partner_name": "Bob Ray",
                    "partner_dupr": 3.8,
                    "partner_registered": True,
                },
                {
                    "firstName": "Cal",
                    "lastName": "Diaz",
                    "email": "cal@example.com",
                    "dupr_rating": 3.5,
                    "partner_email": "dee@example.com",
                    "partner_name": "Dee Fox",
                    "partner_dupr": 3.4,
                    "partner_registered": True,
                },
            ],
        )

        summary = self.service.generate_draw("T1")

        self.assertEqual(summary["format"], "mixed-doubles")
        self.assertEqual(summary["teams"], 2)
        saved = self.tournament_store.update_tournament.call_args[0][1]
        self.assertEqual(len(saved["teams"]), 2)
        self.assertEqual(saved["tournament_status"], "active")


if __name__ == "__main__":
    unittest.main()
