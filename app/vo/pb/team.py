from pydantic import BaseModel
from app.vo.pb.player import Player


class Team(BaseModel):
    team_id: str
    team_name: str
    player_one: Player
    player_two: Player
    score: int
