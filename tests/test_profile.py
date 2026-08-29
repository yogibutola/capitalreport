import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ProfileUpdateRequest


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)
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


class TestClubProfile(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)
        self.club = {
            "_id": "club1",
            "firstName": "Downtown Dinkers",
            "lastName": "Admin",
            "email": "club@example.com",
            "dupr_rating": 0.0,
            "role": "admin",
            "clubName": "Downtown Dinkers",
            "address": "1 Court St",
            "phone": "555-0100",
        }
        self.mock_store.find_player_by_email.return_value = self.club
        self.mock_store.update_player_profile.side_effect = lambda email, updates: {
            **self.club,
            **updates,
        }

    def test_get_profile_returns_club_fields(self):
        resp = self.service.get_profile("club@example.com")
        self.assertEqual(resp.role, "admin")
        self.assertEqual(resp.clubName, "Downtown Dinkers")
        self.assertEqual(resp.address, "1 Court St")
        self.assertEqual(resp.phone, "555-0100")

    def test_update_club_fields_and_sync_first_name(self):
        req = ProfileUpdateRequest(clubName="Uptown Dinkers", address="2 Net Ave", phone="555-0200")
        self.service.update_profile("club@example.com", req)
        _, updates = self.mock_store.update_player_profile.call_args[0]
        self.assertEqual(updates["clubName"], "Uptown Dinkers")
        self.assertEqual(updates["firstName"], "Uptown Dinkers")  # header stays in sync
        self.assertEqual(updates["address"], "2 Net Ave")

    def test_club_player_fields_are_ignored(self):
        req = ProfileUpdateRequest(clubName="Downtown Dinkers", age=40, dupr_rating=5.0, state="CA")
        self.service.update_profile("club@example.com", req)
        _, updates = self.mock_store.update_player_profile.call_args[0]
        self.assertNotIn("age", updates)
        self.assertNotIn("dupr_rating", updates)
        self.assertNotIn("state", updates)

    def test_blank_club_name_rejected(self):
        req = ProfileUpdateRequest(clubName="   ")
        with self.assertRaises(HTTPException) as ctx:
            self.service.update_profile("club@example.com", req)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
