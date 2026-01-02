from pydantic import BaseModel, EmailStr, Field

class LeagueRegistrationPayload(BaseModel):
    """Payload for registering a player for a league"""
    league_id: str = Field(..., description="Unique identifier for the league")
    email: EmailStr = Field(..., description="Email address of the player")
