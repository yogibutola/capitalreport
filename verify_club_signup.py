import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# Add the project root to sys.path
sys.path.append("/Users/yogenderbutola/work/ai/capitalreport")

from app.services.pb_player_service import PBPlayerService
from app.vo.pb.player import ClubSignup

class TestClubSignup(unittest.TestCase):

    @patch('app.services.pb_player_service.PBPlayerStore')
    def test_club_signup_creates_admin(self, MockStore):
        print("\nTesting club signup creates admin...")
        mock_store = MockStore.return_value
        
        # Mock finding existing player (None)
        mock_store.find_player_by_email.return_value = None
        
        # Mock creating player
        mock_store.create_player.side_effect = lambda x: {**x, "_id": "123"}
        
        service = PBPlayerService(mock_store)
        
        club_data = ClubSignup(
            clubName="Pickleball Pro Club",
            email="club@example.com",
            password="securepassword",
            address="123 Main St",
            phone="555-0100"
        )
        
        response = service.register_club(club_data)
        
        # Verify response
        self.assertEqual(response.role, "admin")
        self.assertEqual(response.clubName, "Pickleball Pro Club")
        self.assertEqual(response.firstName, "Pickleball Pro Club")
        self.assertEqual(response.email, "club@example.com")
        
        # Verify store call
        mock_store.create_player.assert_called_once()
        call_args = mock_store.create_player.call_args[0][0]
        self.assertEqual(call_args["role"], "admin")
        self.assertEqual(call_args["clubName"], "Pickleball Pro Club")
        self.assertEqual(call_args["address"], "123 Main St")
        self.assertEqual(call_args["phone"], "555-0100")
        
        print("✓ Club signup verification passed")

    @patch('app.services.pb_player_service.PBPlayerStore')
    def test_club_signup_duplicate_email(self, MockStore):
        print("\nTesting club signup duplicate email...")
        mock_store = MockStore.return_value
        
        # Mock finding existing player
        mock_store.find_player_by_email.return_value = {"_id": "existing"}
        
        service = PBPlayerService(mock_store)
        
        club_data = ClubSignup(
            clubName="Duplicate Club",
            email="existing@example.com",
            password="password"
        )
        
        with self.assertRaises(HTTPException) as cm:
            service.register_club(club_data)
        
        self.assertEqual(cm.exception.status_code, 409)
        print("✓ Duplicate email check passed")

if __name__ == '__main__':
    unittest.main()
