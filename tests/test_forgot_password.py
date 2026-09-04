import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ForgotPasswordRequest, ResetPasswordRequest


class TestForgotPassword(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)

    def test_known_email_issues_and_stores_hashed_token(self):
        self.mock_store.find_player_by_email.return_value = {"email": "user@example.com"}

        self.service.forgot_password(ForgotPasswordRequest(email="user@example.com"))

        self.mock_store.set_reset_token.assert_called_once()
        called_email, called_hash, called_expiry = self.mock_store.set_reset_token.call_args[0]
        self.assertEqual(called_email, "user@example.com")
        self.assertNotEqual(called_hash, "")
        self.assertGreater(called_expiry, datetime.utcnow())

    def test_unknown_email_is_a_silent_noop(self):
        self.mock_store.find_player_by_email.return_value = None

        self.service.forgot_password(ForgotPasswordRequest(email="ghost@example.com"))

        self.mock_store.set_reset_token.assert_not_called()


class TestResetPassword(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)
        self.token = "a-valid-token"
        self.token_hash = self.service._hash_token(self.token)

    def test_valid_token_resets_password(self):
        self.mock_store.find_player_by_reset_token_hash.return_value = {
            "email": "user@example.com",
            "reset_token_hash": self.token_hash,
            "reset_token_expires": datetime.utcnow() + timedelta(minutes=10),
        }

        req = ResetPasswordRequest(token=self.token, new_password="NewPass@2")
        self.service.reset_password(req)

        self.mock_store.reset_password.assert_called_once()
        called_email, called_hash = self.mock_store.reset_password.call_args[0]
        self.assertEqual(called_email, "user@example.com")
        self.assertTrue(self.service.verify_password("NewPass@2", called_hash))

    def test_expired_token_raises_400(self):
        self.mock_store.find_player_by_reset_token_hash.return_value = {
            "email": "user@example.com",
            "reset_token_hash": self.token_hash,
            "reset_token_expires": datetime.utcnow() - timedelta(minutes=1),
        }

        req = ResetPasswordRequest(token=self.token, new_password="NewPass@2")
        with self.assertRaises(HTTPException) as ctx:
            self.service.reset_password(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_store.reset_password.assert_not_called()

    def test_unknown_token_raises_400(self):
        self.mock_store.find_player_by_reset_token_hash.return_value = None

        req = ResetPasswordRequest(token="bogus-token", new_password="NewPass@2")
        with self.assertRaises(HTTPException) as ctx:
            self.service.reset_password(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_store.reset_password.assert_not_called()

    def test_weak_new_password_rejected_by_model(self):
        with self.assertRaises(ValueError):
            ResetPasswordRequest(token=self.token, new_password="weak")


if __name__ == "__main__":
    unittest.main()
