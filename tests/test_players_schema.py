import unittest
from datetime import datetime

from app.store.mongo.schema.players import (
    PLAYERS_INDEXES,
    PLAYERS_VALIDATOR,
    SCHEMA_VERSION,
    player_v2_problems,
)

NOW = datetime(2026, 10, 2, 12, 0)


def valid_player(**overrides) -> dict:
    doc = {
        "email": "pat@example.com", "password_hash": "$2b$12$hash", "firstName": "Pat",
        "lastName": "Lee", "dupr_rating": 3.75, "age": 41, "state": "OR", "city": "Portland",
        "zip_code": "97205", "paddles": [{"brand": "Selkirk", "model": None}],
        "is_demo": False, "created_at": NOW, "updated_at": NOW, "deleted_at": None,
        "schema_version": SCHEMA_VERSION,
    }
    doc.update(overrides)
    return doc


class TestPlayerV2Problems(unittest.TestCase):
    def test_a_complete_profile_is_valid(self):
        self.assertEqual(player_v2_problems(valid_player()), [])

    def test_optional_fields_may_be_null(self):
        doc = valid_player(dupr_rating=None, age=None, state=None, city=None, zip_code=None)
        self.assertEqual(player_v2_problems(doc), [])

    def test_every_required_field_is_enforced(self):
        for field in PLAYERS_VALIDATOR["$jsonSchema"]["required"]:
            with self.subTest(field=field):
                doc = valid_player()
                del doc[field]
                self.assertIn(f"missing {field}", player_v2_problems(doc))

    def test_value_rules(self):
        cases = {
            "email": "Pat@Example.com",
            "firstName": "",
            "dupr_rating": 8.5,
            "age": 12,
            "zip_code": "9720",
            "city": "x" * 101,
            "paddles": [{"brand": "A"}] * 4,
            "is_demo": "yes",
            "created_at": "2026-10-02",
            "schema_version": 1,
        }
        for field, bad in cases.items():
            with self.subTest(field=field):
                self.assertNotEqual(player_v2_problems(valid_player(**{field: bad})), [])

    def test_age_and_rating_reject_booleans(self):
        # bool is an int in Python but not a number to Mongo's validator.
        self.assertNotEqual(player_v2_problems(valid_player(age=True)), [])
        self.assertNotEqual(player_v2_problems(valid_player(dupr_rating=False)), [])

    def test_paddle_shape(self):
        self.assertNotEqual(player_v2_problems(valid_player(paddles=[{"model": "X"}])), [])
        self.assertNotEqual(player_v2_problems(valid_player(paddles=None)), [])
        self.assertEqual(player_v2_problems(valid_player(paddles=[])), [])


class TestValidatorAndPythonRulesAgree(unittest.TestCase):
    """The $jsonSchema and player_v2_problems are two copies of one rule set."""

    def setUp(self):
        self.schema = PLAYERS_VALIDATOR["$jsonSchema"]
        self.props = self.schema["properties"]

    def test_numeric_bounds_match(self):
        self.assertEqual((self.props["dupr_rating"]["minimum"], self.props["dupr_rating"]["maximum"]), (0, 8))
        self.assertEqual((self.props["age"]["minimum"], self.props["age"]["maximum"]), (13, 120))
        self.assertEqual(self.props["paddles"]["maxItems"], 3)

    def test_every_property_has_a_python_check(self):
        # Breaking each property in turn must produce at least one problem.
        bad_values = {
            "email": "NOT AN EMAIL", "password_hash": "", "firstName": "", "lastName": "",
            "dupr_rating": -1, "age": 200, "state": "x" * 101, "city": "x" * 101,
            "zip_code": "abc", "paddles": "Selkirk", "reset_token_hash": 5,
            "reset_token_expires": "soon", "is_demo": 1, "created_at": "now",
            "updated_at": "now", "deleted_at": "never", "schema_version": 3,
        }
        self.assertEqual(set(bad_values), set(self.props))
        for field, bad in bad_values.items():
            with self.subTest(field=field):
                self.assertNotEqual(player_v2_problems(valid_player(**{field: bad})), [])

    def test_unknown_fields_are_allowed(self):
        self.assertNotIn("additionalProperties", self.schema)
        self.assertEqual(player_v2_problems(valid_player(favourite_court="3")), [])

    def test_email_is_uniquely_indexed(self):
        email_index = next(i.document for i in PLAYERS_INDEXES if i.document["name"] == "email_unique")
        self.assertEqual(dict(email_index["key"]), {"email": 1})
        self.assertTrue(email_index["unique"])


if __name__ == "__main__":
    unittest.main()
