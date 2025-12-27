from typing import List, Optional
from pydantic import BaseModel, Field
from app.vo.pb.player import Player
from app.vo.pb.round import Round


class   League(BaseModel):
    league_id: Optional[str] = None
    league_name: Optional[str] = Field(None, min_length=3, description="Name of the league")
    league_description: Optional[str] = None
    league_start_date: Optional[str] = Field(None, pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-\d{4}$", description="Start date in mm-dd-yyyy format")
    league_end_date: Optional[str] = None
    league_duration: Optional[str] = Field(None, min_length=1, description="Duration of the league")
    group_size: Optional[int] = Field(None, gt=0, description="Size of the group, must be positive")
    league_status: Optional[str] = None
    match_format: Optional[str] = Field(None, min_length=1, description="Format of the match")
    players: Optional[List[Player]] = Field(default_factory=list)
    rounds: Optional[List[Round]] = Field(default_factory=list)

    @property
    def player_emails(self) -> List[str]:
        """Get a list of all player emails in the league"""
        return [player.email for player in self.players]