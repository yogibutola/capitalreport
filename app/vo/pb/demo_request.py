from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class DemoRequest(BaseModel):
    """Payload for the public "Book a demo" form on the landing site (unauthenticated)."""

    name: str = Field(..., min_length=2, max_length=120, description="Contact's full name")
    email: EmailStr = Field(..., description="Contact's email address")
    club_name: str = Field(..., min_length=2, max_length=160, description="Club or organisation name")
    phone: Optional[str] = Field(None, max_length=40, description="Optional phone number")
    club_size: Optional[str] = Field(
        None, max_length=40, description="Rough club size bucket, e.g. '50-150 players'"
    )
    preferred_time: Optional[str] = Field(
        None, max_length=120, description="Free-text preferred day/time for the call"
    )
    message: Optional[str] = Field(None, max_length=2000, description="Anything else to share")

    @field_validator("name", "club_name", "phone", "club_size", "preferred_time", "message", mode="before")
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("name", "club_name")
    @classmethod
    def _required_after_strip(cls, v, info):
        if not v:
            raise ValueError(f"{info.field_name} must not be blank")
        return v


class DemoRequestResponse(BaseModel):
    request_id: str
    message: str
