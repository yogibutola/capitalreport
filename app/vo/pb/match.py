from datetime import datetime

from app.vo.pb.player import Player
from app.vo.pb.team import Team
from pydantic import BaseModel


class Match(BaseModel):
    match_id: str
    team_one: Team
    team_two: Team
    siting_player: Player
    time: datetime
    court_number: int
    # Use match_status to lock scoring.
    match_status: str = 'YetToPlay | Completed | Cancelled' 
 