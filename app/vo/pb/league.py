from typing import List
from pydantic import BaseModel, Field
from app.vo.pb.player import Player

class   League(BaseModel):
    league_id: int
    league_name: str = Field(..., min_length=3, description="Name of the league, mandatory")
    league_description: str
    league_start_date: str = Field(..., pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-\d{4}$", description="Start date in mm-dd-yyyy format")
    league_end_date: str
    league_duration: str = Field(..., min_length=1, description="Duration of the league")
    group_size: int = Field(..., gt=0, description="Size of the group, must be positive")
    league_status: str
    match_format: str = Field(..., min_length=1, description="Format of the match, mandatory")
    players: List[Player]

    @property
    def player_emails(self) -> List[str]:
        """Get a list of all player emails in the league"""
        return [player.email for player in self.players]