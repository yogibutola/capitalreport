import re
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


class PlayerLeague(BaseModel):
    """Model for league details associated with a player"""
    league_id: str = Field(..., description="Unique identifier for the league")
    league_name: str = Field(..., description="Name of the league")
    league_type: Optional[str] = Field(None, description="Type of the league")
    league_status: Optional[str] = Field(None, description="Status of the player in the league")
    league_start_date: Optional[str] = Field(None, description="Start date of the league")
    league_end_date: Optional[str] = Field(None, description="End date of the league")
    club_name: Optional[str] = Field(None, description="Name of the club that runs the league")
    location: Optional[str] = Field(None, description="Where the league is played")
    rounds: List[dict] = Field(default_factory=list, description="List of rounds in the league")


class PlayerSignup(BaseModel):
    """Model for player signup requests"""
    firstName: str = Field(..., min_length=1, description="Player's first name")
    lastName: str = Field(..., min_length=1, description="Player's last name")
    email: EmailStr = Field(..., description="Player's email address")
    password: str = Field(..., min_length=6, description="Player's password (min 6 characters)")
    dupr_rating: float = Field(..., ge=0.0, le=8.0, description="DUPR rating between 0.0 and 8.0")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Password must contain at least one alphabet')
        if not re.search(r"[@#$]", v):
            raise ValueError('Password must contain at least one special character (@, #, or $)')
        return v


class Player(BaseModel):
    """Model for player stored in database"""
    id: Optional[str] = Field(default=None, description="Player ID (auto-generated)")
    firstName: str
    lastName: str
    email: EmailStr
    password: Optional[str] = None  # This will be hashed
    dupr_rating: Optional[float] = None
    role: str = Field(default="player", description="User role: player or admin")
    age: Optional[int] = Field(default=None, ge=13, le=120, description="Player's age")
    state: Optional[str] = Field(default=None, description="Player's state / province")
    city: Optional[str] = Field(default=None, description="Player's city")
    leagues: List[PlayerLeague] = Field(default_factory=list)
    clubName: Optional[str] = Field(None, description="Name of the club (for admins)")
    address: Optional[str] = Field(None, description="Club address")
    phone: Optional[str] = Field(None, description="Club phone number")


class ClubSignup(BaseModel):
    """Model for club/admin signup requests"""
    clubName: str = Field(..., min_length=1, description="Name of the club")
    email: EmailStr = Field(..., description="Club email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    address: Optional[str] = Field(None, description="Club address")
    phone: Optional[str] = Field(None, description="Club phone number")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Password must contain at least one alphabet')
        if not re.search(r"[@#$]", v):
            raise ValueError('Password must contain at least one special character (@, #, or $)')
        return v


class PlayerResponse(BaseModel):
    """Model for player API responses (without password)"""
    id: str
    firstName: str
    lastName: str
    email: EmailStr
    dupr_rating: float
    role: str = Field(default="player")
    token: Optional[str] = None
    clubName: Optional[str] = None
    leagues: List[PlayerLeague] = Field(default_factory=list)


class PlayerLogin(BaseModel):
    """Model for player login requests"""
    email: EmailStr = Field(..., description="Player's email address")
    password: str = Field(..., description="Player's password")


class ProfileResponse(BaseModel):
    """Authenticated user's profile (never includes the password hash).

    Player accounts populate ``age``/``dupr_rating``/``state``/``city``; club
    (admin) accounts populate ``clubName``/``address``/``phone`` instead. ``role``
    tells the client which shape to render.
    """
    id: str
    firstName: str
    lastName: str
    email: EmailStr
    age: Optional[int] = None
    dupr_rating: Optional[float] = None
    state: Optional[str] = None
    city: Optional[str] = None
    clubName: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    role: str = Field(default="player")
    # Only populated when the email changed and the old token is now stale.
    token: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    """Fields the user may edit on their own profile.

    Every field is optional; only the keys actually sent are applied. Player
    accounts send name/age/dupr_rating/state/city; club accounts send
    clubName/address/phone. Sending ``null`` for a nullable field clears it.
    """
    firstName: Optional[str] = Field(default=None, description="Player's first name")
    lastName: Optional[str] = Field(default=None, description="Player's last name")
    email: Optional[EmailStr] = Field(default=None, description="Account email address")
    age: Optional[int] = Field(default=None, ge=13, le=120, description="Player's age (13-120)")
    dupr_rating: Optional[float] = Field(default=None, ge=0.0, le=8.0, description="DUPR rating 0.0-8.0")
    state: Optional[str] = Field(default=None, max_length=100, description="Player's state / province")
    city: Optional[str] = Field(default=None, max_length=100, description="Player's city")
    clubName: Optional[str] = Field(default=None, max_length=120, description="Club name (admin accounts)")
    address: Optional[str] = Field(default=None, max_length=200, description="Club address (admin accounts)")
    phone: Optional[str] = Field(default=None, max_length=40, description="Club phone number (admin accounts)")


class ChangePasswordRequest(BaseModel):
    """Model for change-password requests (authenticated user)"""
    current_password: str = Field(..., description="The user's current password")
    new_password: str = Field(..., description="The new password to set")

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Password must contain at least one alphabet')
        if not re.search(r"[@#$]", v):
            raise ValueError('Password must contain at least one special character (@, #, or $)')
        return v


class ForgotPasswordRequest(BaseModel):
    """Model for forgot-password requests (unauthenticated)"""
    email: EmailStr = Field(..., description="Account email address to send a reset link to")


class ResetPasswordRequest(BaseModel):
    """Model for reset-password requests (unauthenticated, uses a one-time token)"""
    token: str = Field(..., description="The reset token from the emailed link")
    new_password: str = Field(..., description="The new password to set")

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Password must contain at least one alphabet')
        if not re.search(r"[@#$]", v):
            raise ValueError('Password must contain at least one special character (@, #, or $)')
        return v