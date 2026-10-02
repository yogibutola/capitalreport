from typing import Optional

from pydantic import BaseModel, EmailStr, Field

class LeagueRegistrationPayload(BaseModel):
    """Payload for registering a player for a league"""
    league_id: str = Field(..., description="Unique identifier for the league")
    # Ignored: the router always registers the token's subject. Kept optional so
    # existing clients that still send it don't get a 422.
    email: Optional[EmailStr] = Field(None, description="Ignored; the authenticated player is registered")
