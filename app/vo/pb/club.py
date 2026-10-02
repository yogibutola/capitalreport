"""Clubs and their venues.

A club is its own record, owned by exactly one player account
(``owner_player_id``, unique) - it is no longer a fake row in ``players``. The
owner signs in with their normal account; a session gets ``role="admin"`` and a
``club_id`` claim because the account owns a club.
"""
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _strip_or_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class ClubCreate(BaseModel):
    """Create a club for the signed-in player."""
    name: str = Field(..., min_length=2, max_length=120, description="Club name")
    contact_email: Optional[EmailStr] = Field(None, description="Public contact email (defaults to the owner's)")
    phone: Optional[str] = Field(None, max_length=40, description="Club phone number")
    address: Optional[str] = Field(None, max_length=200, description="Club address")

    _strip = field_validator("name", "phone", "address", mode="before")(_strip_or_none)


class ClubUpdate(BaseModel):
    """Partial update of the caller's club. Only the keys sent are applied."""
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    contact_email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=40)
    address: Optional[str] = Field(None, max_length=200)

    _strip = field_validator("name", "phone", "address", mode="before")(_strip_or_none)


class ClubResponse(BaseModel):
    id: str
    name: str
    slug: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class ClubSessionResponse(BaseModel):
    """A newly created club plus a fresh session token that carries the admin role."""
    club: ClubResponse
    token: str
    role: str = "admin"


class Court(BaseModel):
    number: int = Field(..., ge=1, le=99)
    label: Optional[str] = Field(None, max_length=40)

    _strip = field_validator("label", mode="before")(_strip_or_none)


class VenueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    address: Optional[str] = Field(None, max_length=200)
    zip_code: Optional[str] = Field(None, pattern=r"^\d{5}$")
    courts: List[Court] = Field(default_factory=list, max_length=50)

    _strip = field_validator("name", "address", "zip_code", mode="before")(_strip_or_none)

    @field_validator("courts")
    @classmethod
    def _unique_court_numbers(cls, courts: List[Court]) -> List[Court]:
        numbers = [c.number for c in courts]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Court numbers must be unique within a venue")
        return courts


class VenueResponse(VenueCreate):
    id: str
    club_id: str
