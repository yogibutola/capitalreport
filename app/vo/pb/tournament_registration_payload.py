import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


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


class PublicTournamentRegistrationPayload(BaseModel):
    """Payload for a brand-new user registering for a tournament from a public
    share link (the link embedded on a tournament flyer / image).

    The backend creates the player account from ``firstName``/``lastName``/
    ``email``/``password``/``dupr_rating`` and then registers that account for the
    tournament, honouring the same doubles partner choice as
    :class:`TournamentRegistrationPayload`.
    """

    tournament_id: str = Field(..., description="Unique identifier for the tournament")

    firstName: str = Field(..., min_length=1, description="Player's first name")
    lastName: str = Field(..., min_length=1, description="Player's last name")
    email: EmailStr = Field(..., description="Email for the new player account")
    password: str = Field(..., min_length=8, description="Password for the new account")
    dupr_rating: float = Field(..., ge=0.0, le=8.0, description="DUPR rating between 0.0 and 8.0")

    partner_email: Optional[EmailStr] = Field(None, description="Existing account to partner with (doubles)")
    partner_invite_name: Optional[str] = Field(None, description="Name of an off-platform partner to invite (doubles)")
    partner_invite_email: Optional[EmailStr] = Field(None, description="Email of an off-platform partner to invite (doubles)")
    needs_partner: bool = Field(False, description="Player is looking for a partner (doubles)")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        # Mirrors PlayerSignup so the public form gets the same 422 field errors.
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("Password must contain at least one alphabet")
        if not re.search(r"[@#$]", v):
            raise ValueError("Password must contain at least one special character (@, #, or $)")
        return v
