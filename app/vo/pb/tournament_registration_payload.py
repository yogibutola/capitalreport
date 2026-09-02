from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class TournamentRegistrationPayload(BaseModel):
    """Payload for registering a player for a tournament.

    For singles only ``tournament_id`` (and the authenticated email) matter. For
    doubles the player must supply exactly one of:
      * ``partner_email`` — an existing platform account to pair with,
      * ``partner_invite_email`` (+ ``partner_invite_name``) — invite someone who
        is not on the platform yet,
      * ``needs_partner`` — looking for a partner (paired at draw time).
    Those rules are enforced in the service, which knows the tournament format.
    """

    tournament_id: str = Field(..., description="Unique identifier for the tournament")
    email: Optional[EmailStr] = Field(None, description="Email of the player (defaults to the token subject)")

    partner_email: Optional[EmailStr] = Field(None, description="Existing account to partner with (doubles)")
    partner_invite_name: Optional[str] = Field(None, description="Name of an off-platform partner to invite (doubles)")
    partner_invite_email: Optional[EmailStr] = Field(None, description="Email of an off-platform partner to invite (doubles)")
    needs_partner: bool = Field(False, description="Player is looking for a partner (doubles)")
