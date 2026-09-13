import os
import unittest
from unittest.mock import MagicMock, patch

import jwt
from fastapi import HTTPException

from app.api.v1.deps import get_current_superadmin
from app.services.pb_player_service import PBPlayerService
from app.utils.security import ALGORITHM, SECRET_KEY, is_superadmin_email
from app.vo.pb.player import PlayerLogin


def _request(method: str):
    req = MagicMock()
    req.method = method
    return req


class TestIsSuperadminEmail(unittest.TestCase):
    @patch.dict(os.environ, {"SUPERADMIN_EMAILS": "boss@x.com, Ops@Y.com"})
    def test_allowlist_is_case_insensitive_and_trimmed(self):
        self.assertTrue(is_superadmin_email("boss@x.com"))
        self.assertTrue(is_superadmin_email("OPS@y.com"))
        self.assertFalse(is_superadmin_email("someone@x.com"))

    @patch.dict(os.environ, {}, clear=True)
    def test_empty_allowlist_denies_everyone(self):
        self.assertFalse(is_superadmin_email("boss@x.com"))
        self.assertFalse(is_superadmin_email(None))


class TestSigninElevation(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.service = PBPlayerService(self.store)
        self.service.verify_password = MagicMock(return_value=True)

    def _signin(self, email):
        self.store.find_player_by_email.return_value = {
            "_id": "1", "firstName": "Ops", "lastName": "Admin",
            "email": email, "role": "player", "dupr_rating": 3.0, "password": "x",
        }
        return self.service.signin_player(PlayerLogin(email=email, password="Secret@123"))

    @patch.dict(os.environ, {"SUPERADMIN_EMAILS": "boss@x.com"})
    def test_allowlisted_email_gets_superadmin_role_and_claim(self):
        resp = self._signin("boss@x.com")
        self.assertEqual(resp.role, "superadmin")
        payload = jwt.decode(resp.token, SECRET_KEY, algorithms=[ALGORITHM])
        self.assertEqual(payload["role"], "superadmin")
        self.assertEqual(payload["sub"], "boss@x.com")

    @patch.dict(os.environ, {"SUPERADMIN_EMAILS": "boss@x.com"})
    def test_non_allowlisted_email_keeps_its_role(self):
        resp = self._signin("player@x.com")
        self.assertEqual(resp.role, "player")
        payload = jwt.decode(resp.token, SECRET_KEY, algorithms=[ALGORITHM])
        self.assertEqual(payload["role"], "player")


class TestGetCurrentSuperadminDependency(unittest.TestCase):
    def test_superadmin_payload_passes(self):
        payload = {"sub": "boss@x.com", "role": "superadmin"}
        self.assertIs(get_current_superadmin(_request("GET"), payload), payload)

    def test_club_admin_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_superadmin(_request("GET"), {"sub": "c@x.com", "role": "admin"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_player_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_superadmin(_request("GET"), {"sub": "p@x.com", "role": "player"})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
