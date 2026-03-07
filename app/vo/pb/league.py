from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.vo.pb.player import Player
from app.vo.pb.round import Round


class Withdrawal(BaseModel):
    email: str = Field(..., description="Email of the withdrawn player")
    play_day: int = Field(..., description="The play day the player is withdrawn from")
    reason: str = Field(..., description="Reason for withdrawal")


class   League(BaseModel):
    league_id: Optional[str] = None
    
    @field_validator('league_id', mode='before')
    @classmethod
    def check_league_id(cls, v):
        if v == 0:
            return None
        return v
    league_name: str = Field(..., min_length=3, description="Name of the league")
    league_description: Optional[str] = None
    league_start_date: str = Field(..., pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-\d{4}$", description="Start date in mm-dd-yyyy format")
    league_end_date: Optional[str] = None
    league_duration: Optional[str] = Field(None, min_length=1, description="Duration of the league")
    group_size: int = Field(..., gt=0, description="Size of the group, must be positive")
    league_status: Optional[str] = None
    match_format: str = Field(..., min_length=1, description="Format of the match")
    players: Optional[List[Player]] = Field(default_factory=list)
    rounds: Optional[List[Round]] = Field(default_factory=list)
    withdrawals: Optional[List[Withdrawal]] = Field(default_factory=list, description="List of player withdrawals per play day")

    @property
    def player_emails(self) -> List[str]:
        """Get a list of all player emails in the league"""
        return [player.email for player in self.players]