import unittest
from unittest.mock import MagicMock, patch

import pydantic
from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ClubSignup, PlayerSignup

PASSWORD = "Passw0rd@1"


def signup(**overrides):
    return PlayerSignup(firstName="Ada", lastName="Lovelace", email="ada@example.com",
                        password=PASSWORD, dupr_rating=3.5, **overrides)


class PlayerSignupLocationTestCase(unittest.TestCase):
    """Location at signup is optional, but a ZIP that IS given has to be real -
    otherwise the account is silently invisible to distance search."""

    def setUp(self):
        self.mock_store = MagicMock()
        self.mock_store.find_player_by_email.return_value = None  # email is free
        self.mock_store.create_player.side_effect = lambda data: {**data, "_id": "new-id"}
        self.service = PBPlayerService(self.mock_store)

    def register(self, req, known_zip=True):
        with patch('app.services.pb_player_service.zip_is_known', return_value=known_zip):
            return self.service.register_player(req)

    def stored(self):
        return self.mock_store.create_player.call_args[0][0]


class TestLocationIsPersisted(PlayerSignupLocationTestCase):
    def test_city_state_and_zip_are_stored(self):
        self.register(signup(city="Ashburn", state="VA", zip_code="20147"))
        doc = self.stored()
        self.assertEqual(doc["city"], "Ashburn")
        self.assertEqual(doc["state"], "VA")
        self.assertEqual(doc["zip_code"], "20147")

    def test_zip_plus_four_is_normalized_to_five_digits(self):
        self.register(signup(zip_code="20147-1234"))
        self.assertEqual(self.stored()["zip_code"], "20147")

    def test_free_text_fields_are_trimmed(self):
        self.register(signup(city="  Ashburn  ", state=" VA "))
        doc = self.stored()
        self.assertEqual(doc["city"], "Ashburn")
        self.assertEqual(doc["state"], "VA")

    def test_omitted_location_is_none_not_empty_string(self):
        """None keeps "no location" distinguishable from "blank location", and is
        what the distance filter checks for."""
        self.register(signup())
        doc = self.stored()
        for key in ("city", "state", "zip_code"):
            self.assertIsNone(doc[key], key)

    def test_blank_location_collapses_to_none(self):
        self.register(signup(city="   ", state="", zip_code="  "))
        doc = self.stored()
        for key in ("city", "state", "zip_code"):
            self.assertIsNone(doc[key], key)

    def test_signup_without_any_location_still_succeeds(self):
        resp = self.register(signup())
        self.assertEqual(resp.email, "ada@example.com")
        self.mock_store.create_player.assert_called_once()


class TestZipValidation(PlayerSignupLocationTestCase):
    def test_a_malformed_zip_is_rejected_by_the_model(self):
        with self.assertRaises(pydantic.ValidationError) as ctx:
            signup(zip_code="abc")
        error = ctx.exception.errors()[0]
        self.assertEqual(error["loc"], ("zip_code",))
        self.assertIn("5-digit", error["msg"])

    def test_a_wrong_length_zip_is_rejected_by_the_model(self):
        for bad in ("2014", "201478"):
            with self.subTest(zip_code=bad), self.assertRaises(pydantic.ValidationError):
                signup(zip_code=bad)

    def test_an_unrecognised_zip_is_a_422_on_the_zip_field(self):
        with self.assertRaises(HTTPException) as ctx:
            self.register(signup(zip_code="00000"), known_zip=False)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail[0]["loc"], ["body", "zip_code"])
        self.mock_store.create_player.assert_not_called()

    def test_no_zip_means_no_lookup(self):
        """Location is optional, so an absent ZIP must not trip the "unknown" check."""
        with patch('app.services.pb_player_service.zip_is_known') as known:
            self.service.register_player(signup())
        known.assert_not_called()


class TestClubSignupIsUnaffected(PlayerSignupLocationTestCase):
    def test_club_signup_has_no_location_fields(self):
        """Clubs carry address/phone instead; they must not gain a player ZIP."""
        for field in ("zip_code", "city", "state"):
            self.assertNotIn(field, ClubSignup.model_fields)

    def test_registering_a_club_stores_no_zip(self):
        self.service.register_club(ClubSignup(
            clubName="Metro Paddle", email="club@example.com",
            password=PASSWORD, address="1 Main St", phone="555-0100"))
        self.assertIsNone(self.stored().get("zip_code"))


if __name__ == "__main__":
    unittest.main()
