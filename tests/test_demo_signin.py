import unittest
from unittest.mock import MagicMock

import jwt
from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService, DEMO_ACCOUNTS
from app.utils.security import ALGORITHM, SECRET_KEY


class TestDemoSignin(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)

    def _decode(self, token: str) -> dict:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_admin_persona_returns_demo_admin_session(self):
        self.mock_store.find_player_by_email.return_value = {
            "_id": "1", "firstName": "StackedPaddle Demo Club", "lastName": "Admin",
            "email": DEMO_ACCOUNTS["admin"], "role": "admin", "dupr_rating": 0.0,
            "clubName": "StackedPaddle Demo Club",
        }

        resp = self.service.demo_signin("admin")

        self.mock_store.find_player_by_email.assert_called_once_with(DEMO_ACCOUNTS["admin"])
        self.assertTrue(resp.is_demo)
        self.assertEqual(resp.role, "admin")
        payload = self._decode(resp.token)
        self.assertTrue(payload["demo"])
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["sub"], DEMO_ACCOUNTS["admin"])

    def test_player_persona_returns_demo_player_session(self):
        self.mock_store.find_player_by_email.return_value = {
            "_id": "2", "firstName": "Demo", "lastName": "Player",
            "email": DEMO_ACCOUNTS["player"], "role": "player", "dupr_rating": 3.5,
        }

        resp = self.service.demo_signin("player")

        self.assertTrue(resp.is_demo)
        self.assertEqual(resp.role, "player")
        self.assertTrue(self._decode(resp.token)["demo"])

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
