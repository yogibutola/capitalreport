import unittest
from unittest.mock import MagicMock, patch

import pydantic
from bson import ObjectId
from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ProfileUpdateRequest


def _no_club():
    """A club store in which the account runs no club."""
    clubs = MagicMock()
    clubs.get_club_by_owner.return_value = None
    return clubs


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store, _no_club())
        self.player = {
            "_id": "abc123",
            "firstName": "Ada",
            "lastName": "Lovelace",
            "email": "ada@example.com",
            "dupr_rating": 3.5,
            "role": "player",
        }
        self.mock_store.find_player_by_email.return_value = self.player
        # update_player_profile echoes back a merged doc
        self.mock_store.update_player_profile.side_effect = lambda email, updates: {
            **self.player,
            **updates,
        }

    def test_get_profile_returns_fields(self):
        resp = self.service.get_profile("ada@example.com")
        self.assertEqual(resp.firstName, "Ada")
        self.assertEqual(resp.email, "ada@example.com")
        self.assertIsNone(resp.token)

    def test_get_profile_unknown_user_404(self):
        self.mock_store.find_player_by_email.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_profile("ghost@example.com")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_update_basic_fields(self):
        req = ProfileUpdateRequest(firstName="Ada", lastName="King", age=36, state="CA", city="Palo Alto")
        resp = self.service.update_profile("ada@example.com", req)
        email, updates = self.mock_store.update_player_profile.call_args[0]
        self.assertEqual(email, "ada@example.com")
        self.assertEqual(updates["lastName"], "King")
        self.assertEqual(updates["age"], 36)
        self.assertEqual(updates["city"], "Palo Alto")
        self.assertNotIn("email", updates)  # unchanged email is dropped
        self.assertIsNone(resp.token)

    def test_blank_name_rejected(self):
        req = ProfileUpdateRequest(firstName="   ")
        with self.assertRaises(HTTPException) as ctx:
            self.service.update_profile("ada@example.com", req)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_email_change_checks_conflict(self):
        self.mock_store.find_player_by_email.side_effect = [
            self.player,          # lookup of current user
            {"email": "taken@example.com"},  # the new email is taken
        ]
        req = ProfileUpdateRequest(email="taken@example.com")
        with self.assertRaises(HTTPException) as ctx:
            self.service.update_profile("ada@example.com", req)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_email_change_issues_new_token(self):
        self.mock_store.find_player_by_email.side_effect = [self.player, None]
        req = ProfileUpdateRequest(email="Ada.New@example.com")
        resp = self.service.update_profile("ada@example.com", req)
        _, updates = self.mock_store.update_player_profile.call_args[0]
        self.assertEqual(updates["email"], "ada.new@example.com")
        self.assertTrue(resp.token)

    def test_age_out_of_range_rejected_by_model(self):
        with self.assertRaises(ValueError):
            ProfileUpdateRequest(age=5)

    def test_dupr_out_of_range_rejected_by_model(self):
        with self.assertRaises(ValueError):
            ProfileUpdateRequest(dupr_rating=12.0)


class TestClubOwnerProfile(unittest.TestCase):
    """A club owner is a person with a player profile who also runs a club record.
    The profile page edits both: player fields go to the account, club fields to the club."""

    def setUp(self):
        self.mock_store = MagicMock()
        self.clubs = MagicMock()
        self.service = PBPlayerService(self.mock_store, self.clubs)
        self.owner = {
            "_id": ObjectId(), "firstName": "Dana", "lastName": "Dink",
            "email": "dana@example.com", "dupr_rating": 4.0,
        }
        self.club = {"_id": ObjectId(), "name": "Downtown Dinkers", "address": "1 Court St", "phone": "555-0100"}
        self.mock_store.find_player_by_email.return_value = self.owner
        self.mock_store.update_player_profile.side_effect = lambda email, updates: {**self.owner, **updates}
        self.clubs.get_club_by_owner.return_value = self.club
        self.clubs.update_club.side_effect = lambda club_id, fields: {**self.club, **fields}

    def test_get_profile_returns_the_owners_club(self):
        resp = self.service.get_profile("dana@example.com")
        self.assertEqual(resp.role, "admin")
        self.assertEqual(resp.firstName, "Dana")
        self.assertEqual(resp.clubName, "Downtown Dinkers")
        self.assertEqual(resp.address, "1 Court St")
        self.assertEqual(resp.phone, "555-0100")

    def test_club_fields_update_the_club_record_not_the_account(self):
        req = ProfileUpdateRequest(clubName="Uptown Dinkers", address="2 Net Ave", phone="555-0200")
        resp = self.service.update_profile("dana@example.com", req)
        club_id, fields = self.clubs.update_club.call_args[0]
        self.assertEqual(club_id, self.club["_id"])
        self.assertEqual(fields, {"name": "Uptown Dinkers", "address": "2 Net Ave", "phone": "555-0200"})
        _, account_updates = self.mock_store.update_player_profile.call_args[0]
        for key in ("clubName", "name", "address", "phone"):
            self.assertNotIn(key, account_updates)
        self.assertEqual(resp.clubName, "Uptown Dinkers")

    def test_an_owner_can_still_edit_their_player_profile(self):
        req = ProfileUpdateRequest(firstName="Danielle", dupr_rating=4.25, paddles=[{"brand": "Joola"}])
        self.service.update_profile("dana@example.com", req)
        _, updates = self.mock_store.update_player_profile.call_args[0]
        self.assertEqual(updates["firstName"], "Danielle")
        self.assertEqual(updates["dupr_rating"], 4.25)
        self.assertEqual(updates["paddles"], [{"brand": "Joola", "model": None}])

    def test_blank_club_name_rejected(self):
        req = ProfileUpdateRequest(clubName="   ")
        with self.assertRaises(HTTPException) as ctx:
            self.service.update_profile("dana@example.com", req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.clubs.update_club.assert_not_called()

    def test_club_fields_are_ignored_for_someone_without_a_club(self):
        self.clubs.get_club_by_owner.return_value = None
        resp = self.service.update_profile("dana@example.com", ProfileUpdateRequest(clubName="Mine Now"))
        self.clubs.update_club.assert_not_called()
        self.assertIsNone(resp.clubName)
        self.assertEqual(resp.role, "player")


class TestProfileZipCode(unittest.TestCase):
    """The ZIP is what anchors a player in distance search, so it is normalized on
    the way in and has to name a real place."""

    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store, _no_club())
        self.player = {
            "_id": "abc123", "firstName": "Ada", "lastName": "Lovelace",
            "email": "ada@example.com", "dupr_rating": 3.5, "role": "player",
            "zip_code": "20147",
        }
        self.mock_store.find_player_by_email.return_value = self.player
        self.mock_store.update_player_profile.side_effect = lambda email, updates: {
            **self.player, **updates,
        }

    def update(self, req, known_zip=True):
        with patch('app.services.pb_player_service.zip_is_known', return_value=known_zip):
            return self.service.update_profile("ada@example.com", req)

    def updates(self):
        return self.mock_store.update_player_profile.call_args[0][1]

    def test_zip_is_returned_on_the_profile(self):
        self.assertEqual(self.service.get_profile("ada@example.com").zip_code, "20147")

    def test_zip_plus_four_is_stored_as_five_digits(self):
        self.update(ProfileUpdateRequest(zip_code="20147-1234"))
        self.assertEqual(self.updates()["zip_code"], "20147")

    def test_surrounding_whitespace_is_stripped(self):
        self.update(ProfileUpdateRequest(zip_code="  20147  "))
        self.assertEqual(self.updates()["zip_code"], "20147")

    def test_empty_string_clears_the_zip(self):
        """The profile form sends '' rather than null when a field is cleared, so
        this is the only way a player can remove their ZIP."""
        self.update(ProfileUpdateRequest(zip_code=""))
        self.assertIsNone(self.updates()["zip_code"])

    def test_a_malformed_zip_is_rejected_by_the_model(self):
        with self.assertRaises(pydantic.ValidationError) as ctx:
            ProfileUpdateRequest(zip_code="not-a-zip")
        self.assertEqual(ctx.exception.errors()[0]["loc"], ("zip_code",))

    def test_an_unrecognised_zip_is_a_422_on_the_zip_field(self):
        with self.assertRaises(HTTPException) as ctx:
            self.update(ProfileUpdateRequest(zip_code="00000"), known_zip=False)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail[0]["loc"], ["body", "zip_code"])
        self.mock_store.update_player_profile.assert_not_called()

    def test_clearing_the_zip_does_not_trip_the_unknown_check(self):
        with patch('app.services.pb_player_service.zip_is_known') as known:
            self.service.update_profile("ada@example.com", ProfileUpdateRequest(zip_code=""))
        known.assert_not_called()

    def test_an_update_that_omits_the_zip_leaves_it_alone(self):
        self.update(ProfileUpdateRequest(city="Ashburn"))
        self.assertNotIn("zip_code", self.updates())


class TestProfilePaddles(unittest.TestCase):
    """The paddle bag is free-text brand + optional model, tidied on the way in."""

    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store, _no_club())
        self.player = {
            "_id": "abc123", "firstName": "Ada", "lastName": "Lovelace",
            "email": "ada@example.com", "dupr_rating": 3.5, "role": "player",
            "paddles": [{"brand": "Joola", "model": "Perseus"}],
        }
        self.mock_store.find_player_by_email.return_value = self.player
        self.mock_store.update_player_profile.side_effect = lambda email, updates: {
            **self.player, **updates,
        }

    def update(self, req):
        return self.service.update_profile("ada@example.com", req)

    def updates(self):
        return self.mock_store.update_player_profile.call_args[0][1]

    # ---- reads ----

    def test_paddles_are_returned_on_the_profile(self):
        paddles = self.service.get_profile("ada@example.com").paddles
        self.assertEqual(len(paddles), 1)
        self.assertEqual(paddles[0].brand, "Joola")
        self.assertEqual(paddles[0].model, "Perseus")

    def test_a_legacy_player_without_the_field_gets_an_empty_list(self):
        del self.player["paddles"]
        self.assertEqual(self.service.get_profile("ada@example.com").paddles, [])

    def test_a_stored_null_becomes_an_empty_list(self):
        self.player["paddles"] = None
        self.assertEqual(self.service.get_profile("ada@example.com").paddles, [])

    # ---- normalization ----

    def test_brand_and_model_are_trimmed(self):
        self.update(ProfileUpdateRequest(paddles=[{"brand": "  CRBN  ", "model": "  1X  "}]))
        self.assertEqual(self.updates()["paddles"], [{"brand": "CRBN", "model": "1X"}])

    def test_a_blank_model_becomes_none(self):
        self.update(ProfileUpdateRequest(paddles=[{"brand": "CRBN", "model": "   "}]))
        self.assertEqual(self.updates()["paddles"], [{"brand": "CRBN", "model": None}])

    def test_an_entry_with_a_blank_brand_is_dropped(self):
        """A model on its own can't be rendered as a chip."""
        self.update(ProfileUpdateRequest(paddles=[
            {"brand": "   ", "model": "Perseus"},
            {"brand": "Selkirk", "model": None},
        ]))
        self.assertEqual(self.updates()["paddles"], [{"brand": "Selkirk", "model": None}])

    def test_duplicate_paddles_are_collapsed_case_insensitively(self):
        self.update(ProfileUpdateRequest(paddles=[
            {"brand": "Joola", "model": "Perseus"},
            {"brand": "joola", "model": "perseus"},
        ]))
        # First spelling wins.
        self.assertEqual(self.updates()["paddles"], [{"brand": "Joola", "model": "Perseus"}])

    def test_the_same_brand_with_different_models_is_not_a_duplicate(self):
        self.update(ProfileUpdateRequest(paddles=[
            {"brand": "Joola", "model": "Perseus"},
            {"brand": "Joola", "model": "Hyperion"},
        ]))
        self.assertEqual(len(self.updates()["paddles"]), 2)

    def test_order_is_preserved(self):
        self.update(ProfileUpdateRequest(paddles=[
            {"brand": "Selkirk"}, {"brand": "CRBN"}, {"brand": "Engage"},
        ]))
        self.assertEqual([p["brand"] for p in self.updates()["paddles"]],
                         ["Selkirk", "CRBN", "Engage"])

    def test_paddles_are_stored_as_plain_dicts(self):
        """$set has to write BSON, not Pydantic objects."""
        self.update(ProfileUpdateRequest(paddles=[{"brand": "CRBN"}]))
        self.assertIsInstance(self.updates()["paddles"][0], dict)

    # ---- the clear-all contract ----

    def test_an_empty_list_clears_the_paddles(self):
        self.update(ProfileUpdateRequest(paddles=[]))
        self.assertEqual(self.updates()["paddles"], [])

    def test_null_is_treated_as_clear_not_as_omit(self):
        self.update(ProfileUpdateRequest(paddles=None))
        self.assertEqual(self.updates()["paddles"], [])

    def test_an_update_that_omits_paddles_leaves_them_alone(self):
        self.update(ProfileUpdateRequest(city="Ashburn"))
        self.assertNotIn("paddles", self.updates())

    # ---- model constraints ----

    def test_more_than_three_paddles_is_rejected_by_the_model(self):
        with self.assertRaises(pydantic.ValidationError) as ctx:
            ProfileUpdateRequest(paddles=[{"brand": b} for b in "abcd"])
        self.assertEqual(ctx.exception.errors()[0]["loc"], ("paddles",))

    def test_an_over_long_brand_is_rejected_by_the_model(self):
        with self.assertRaises(pydantic.ValidationError):
            ProfileUpdateRequest(paddles=[{"brand": "x" * 41}])

    def test_an_over_long_model_is_rejected_by_the_model(self):
        with self.assertRaises(pydantic.ValidationError):
            ProfileUpdateRequest(paddles=[{"brand": "CRBN", "model": "x" * 61}])



if __name__ == "__main__":
    unittest.main()
