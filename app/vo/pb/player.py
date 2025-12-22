from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class PlayerSignup(BaseModel):
    """Model for player signup requests"""
    firstName: str = Field(..., min_length=1, description="Player's first name")
    lastName: str = Field(..., min_length=1, description="Player's last name")
    email: EmailStr = Field(..., description="Player's email address")
    password: str = Field(..., min_length=6, description="Player's password (min 6 characters)")
    dupr_rating: float = Field(..., ge=0.0, le=8.0, description="DUPR rating between 0.0 and 8.0")


class Player(BaseModel):
    """Model for player stored in database"""
    id: Optional[str] = Field(default=None, description="Player ID (auto-generated)")
    firstName: str
    lastName: str
    email: EmailStr
    password: str  # This will be hashed
    dupr_rating: float


class PlayerResponse(BaseModel):
    """Model for player API responses (without password)"""
    id: str
    firstName: str
    lastName: str
    email: EmailStr
    dupr_rating: float