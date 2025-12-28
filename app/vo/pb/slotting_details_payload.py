from pydantic import BaseModel

class MatchDetailsPayload(BaseModel):
    match_id: str
    score_team_1: int
    score_team_2: int
    league_name: str
    round_id: str
    group_id: str
