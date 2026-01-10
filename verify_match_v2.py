from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# Mocking parts of the app to test the Match model
class Player(BaseModel):
    email: str
    firstName: str
    lastName: str
    dupr_rating: Optional[float] = None

class Team(BaseModel):
    team_id: str
    team_name: str
    player_one: Player
    player_two: Player
    score: int

class Match(BaseModel):
    league_id: str
    league_name: str
    round_id: str
    group_id: str
    match_id: str
    team_one: Team
    team_two: Team
    siting_player: Optional[Player] = None
    time: Optional[datetime] = None
    court_number: Optional[int] = None
    match_status: str = 'YetToPlay | Completed | Cancelled'

def test_match_optional():
    p1 = Player(email="p1@test.com", firstName="P1", lastName="T1")
    p2 = Player(email="p2@test.com", firstName="P2", lastName="T1")
    t1 = Team(team_id="t1", team_name="Team 1", player_one=p1, player_two=p2, score=0)
    t2 = Team(team_id="t2", team_name="Team 2", player_one=p1, player_two=p2, score=0)
    
    m = Match(
        league_id="l1",
        league_name="League 1",
        round_id="r1",
        group_id="g1",
        match_id="m1",
        team_one=t1,
        team_two=t2
    )
    
    print("Match created successfully without time and court_number")
    assert m.time is None
    assert m.court_number is None
    assert m.match_status == 'YetToPlay | Completed | Cancelled'
    print("Verification passed!")

if __name__ == "__main__":
    test_match_optional()
