from pydantic import BaseModel

class MatchDetailsPayload(BaseModel):
    league_id: str
    match_id: str
    score_team_1: int
    score_team_2: int
    match_status: str
