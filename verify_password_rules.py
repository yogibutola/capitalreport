import sys
import unittest
from pydantic import ValidationError

# Add the project root to sys.path
sys.path.append("/Users/yogenderbutola/work/ai/capitalreport")

from app.vo.pb.player import PlayerSignup, ClubSignup

class TestPasswordRules(unittest.TestCase):

    def test_valid_password(self):
        print("\nTesting valid password...")
        # 8+ chars, 1 Upper, 1 Number, 1 Special (@#$)
        valid_pass = "Valid1@Pass"
        
        try:
            PlayerSignup(
                firstName="Test",
                lastName="User",
                email="test@example.com",
                password=valid_pass,
                dupr_rating=4.0
            )
            print("✓ Valid password accepted")
        except ValidationError as e:
            self.fail(f"Valid password rejected: {e}")

    def test_too_short(self):
        print("\nTesting password too short...")
        invalid_pass = "Short1@"
        with self.assertRaises(ValidationError) as cm:
            PlayerSignup(
                firstName="Test",
                lastName="User",
                email="test@example.com",
                password=invalid_pass,
                dupr_rating=4.0
            )
        self.assertIn("at least 8 characters", str(cm.exception))
        print("✓ Short password rejected")

    def test_missing_uppercase(self):
        print("\nTesting missing uppercase...")
        invalid_pass = "lower1@pass"
        with self.assertRaises(ValidationError) as cm:
            PlayerSignup(
                firstName="Test",
                lastName="User",
                email="test@example.com",
                password=invalid_pass,
                dupr_rating=4.0
            )
        self.assertIn("uppercase letter", str(cm.exception))
        print("✓ Missing uppercase rejected")

    def test_missing_number(self):
        print("\nTesting missing number...")
        invalid_pass = "NoNumber@Pass"
        with self.assertRaises(ValidationError) as cm:
            PlayerSignup(
                firstName="Test",
                lastName="User",
                email="test@example.com",
                password=invalid_pass,
                dupr_rating=4.0
            )
        self.assertIn("at least one number", str(cm.exception))
        print("✓ Missing number rejected")

    def test_missing_special(self):
        print("\nTesting missing special char...")
        invalid_pass = "NoSpecial1Pass"
        with self.assertRaises(ValidationError) as cm:
            PlayerSignup(
                firstName="Test",
                lastName="User",
                email="test@example.com",
                password=invalid_pass,
                dupr_rating=4.0
            )
        self.assertIn("special character", str(cm.exception))
        print("✓ Missing special char rejected")
        
    def test_club_signup_validation(self):
        print("\nTesting ClubSignup validation...")
        invalid_pass = "weak"
        with self.assertRaises(ValidationError):
            ClubSignup(
                clubName="Club",
                email="club@example.com",
                password=invalid_pass
            )
        print("✓ ClubSignup validation active")

if __name__ == '__main__':
    unittest.main()
