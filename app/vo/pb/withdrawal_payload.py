from pydantic import BaseModel, Field, EmailStr

class WithdrawalPayload(BaseModel):
    """Model for a player to request a withdrawal for a specific play day"""
    league_id: str = Field(..., description="ID of the league")
    play_day: int = Field(..., description="The play day number to withdraw from (e.g., 1 for rounds 1 & 2)")
    reason: str = Field(..., min_length=1, description="Reason for withdrawal")
