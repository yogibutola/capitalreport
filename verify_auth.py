import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# Add the project root to sys.path
sys.path.append("/Users/yogenderbutola/work/ai/capitalreport")

from app.utils.security import create_access_token, verify_token
from app.api.v1.deps import get_current_player, get_current_admin
from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import PlayerSignup, PlayerLogin

class TestAuth(unittest.TestCase):
    
    def test_token_creation_and_verification(self):
        print("\nTesting token creation and verification...")
        data = {"sub": "test@example.com", "role": "player"}
        token = create_access_token(data)
        decoded = verify_token(token)
        self.assertEqual(decoded["sub"], "test@example.com")
        self.assertEqual(decoded["role"], "player")
        print("✓ Token creation and verification passed")

    def test_admin_dependency_success(self):
        print("\nTesting admin dependency (success)...")
        payload = {"sub": "admin@example.com", "role": "admin"}
        result = get_current_admin(payload)
        self.assertEqual(result, payload)
        print("✓ Admin dependency success passed")

    def test_admin_dependency_failure(self):
        print("\nTesting admin dependency (failure)...")
        payload = {"sub": "player@example.com", "role": "player"}
        with self.assertRaises(HTTPException) as cm:
            get_current_admin(payload)
        self.assertEqual(cm.exception.status_code, 403)
        print("✓ Admin dependency failure passed")

    @patch('app.services.pb_player_service.PBPlayerStore')
    def test_service_signin_generates_token(self, MockStore):
        print("\nTesting service signin generates token...")
        mock_store = MockStore.return_value
        # Mock finding a player
        mock_store.find_player_by_email.return_value = {
            "_id": "123",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "password": "hashed_password", # Mocked below
            "dupr_rating": 4.5,
            "role": "player"
        }
        
        service = PBPlayerService(mock_store)
        # Mock password verification to return True
        service.verify_password = MagicMock(return_value=True)
        
        login_data = PlayerLogin(email="john@example.com", password="password")
        response = service.signin_player(login_data)
        
        self.assertIsNotNone(response.token)
        decoded = verify_token(response.token)
        self.assertEqual(decoded["sub"], "john@example.com")
        print("✓ Service signin token generation passed")

if __name__ == '__main__':
    unittest.main()
