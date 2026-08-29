import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ChangePasswordRequest


class TestChangePassword(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBPlayerService(self.mock_store)
        self.current_plain = "OldPass@1"
        self.mock_store.find_player_by_email.return_value = {
            "email": "user@example.com",
            "password": self.service.hash_password(self.current_plain),
        }

    def test_valid_change_updates_password(self):
        req = ChangePasswordRequest(current_password=self.current_plain, new_password="NewPass@2")
        self.service.change_password("user@example.com", req)

        self.mock_store.update_player_password.assert_called_once()
        called_email, called_hash = self.mock_store.update_player_password.call_args[0]
        self.assertEqual(called_email, "user@example.com")
        self.assertTrue(self.service.verify_password("NewPass@2", called_hash))

    def test_wrong_current_password_raises_400(self):
        req = ChangePasswordRequest(current_password="WrongPass@9", new_password="NewPass@2")
        with self.assertRaises(HTTPException) as ctx:
            self.service.change_password("user@example.com", req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_store.update_player_password.assert_not_called()

    def test_new_password_same_as_current_raises_400(self):
        req = ChangePasswordRequest(current_password=self.current_plain, new_password=self.current_plain)
        with self.assertRaises(HTTPException) as ctx:
            self.service.change_password("user@example.com", req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.mock_store.update_player_password.assert_not_called()

    def test_unknown_user_raises_404(self):
        self.mock_store.find_player_by_email.return_value = None
        req = ChangePasswordRequest(current_password=self.current_plain, new_password="NewPass@2")
        with self.assertRaises(HTTPException) as ctx:
            self.service.change_password("ghost@example.com", req)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_weak_new_password_rejected_by_model(self):
        with self.assertRaises(ValueError):
            ChangePasswordRequest(current_password=self.current_plain, new_password="weak")


if __name__ == "__main__":
    unittest.main()
