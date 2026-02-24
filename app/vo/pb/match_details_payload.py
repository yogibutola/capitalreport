from pydantic import BaseModel
from typing import Optional

class MatchDetailsPayload(BaseModel):
    league_id: str
    match_id: str
    score_team_1: int
    team_1_name: Optional[str] = None
    score_team_2: int
    team_2_name: Optional[str] = None
    match_status: str
