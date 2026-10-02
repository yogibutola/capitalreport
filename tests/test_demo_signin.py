import unittest
from unittest.mock import MagicMock

import jwt
from bson import ObjectId
from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService, DEMO_ACCOUNTS
from app.utils.security import ALGORITHM, SECRET_KEY


class TestDemoSignin(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.clubs = MagicMock()
        self.clubs.get_club_by_owner.return_value = None
        self.service = PBPlayerService(self.mock_store, self.clubs)

    def _decode(self, token: str) -> dict:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_admin_persona_returns_demo_admin_session(self):
        owner_id, club_id = ObjectId(), ObjectId()
        # The demo organiser is a normal account; "admin" comes from owning the demo club.
        self.mock_store.find_player_by_email.return_value = {
            "_id": owner_id, "firstName": "Demo", "lastName": "Organiser",
            "email": DEMO_ACCOUNTS["admin"], "dupr_rating": None,
        }
        self.clubs.get_club_by_owner.return_value = {"_id": club_id, "name": "StackedPaddle Demo Club"}

        resp = self.service.demo_signin("admin")

        self.mock_store.find_player_by_email.assert_called_once_with(DEMO_ACCOUNTS["admin"])
        self.assertTrue(resp.is_demo)
        self.assertEqual(resp.role, "admin")
        payload = self._decode(resp.token)
        self.assertTrue(payload["demo"])
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["club_id"], str(club_id))
        self.assertEqual(payload["sub"], DEMO_ACCOUNTS["admin"])
        self.assertEqual(resp.clubName, "StackedPaddle Demo Club")
        self.clubs.get_club_by_owner.assert_called_once_with(owner_id)

    def test_player_persona_returns_demo_player_session(self):
        self.mock_store.find_player_by_email.return_value = {
            "_id": ObjectId(), "firstName": "Demo", "lastName": "Player",
            "email": DEMO_ACCOUNTS["player"], "dupr_rating": 3.5,
        }

        resp = self.service.demo_signin("player")

        self.assertTrue(resp.is_demo)
        self.assertEqual(resp.role, "player")
        payload = self._decode(resp.token)
        self.assertTrue(payload["demo"])
        self.assertNotIn("club_id", payload)

    def test_unknown_persona_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.demo_signin("superadmin")
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_store.find_player_by_email.assert_not_called()

    def test_unseeded_environment_returns_404(self):
        self.mock_store.find_player_by_email.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.service.demo_signin("admin")
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
