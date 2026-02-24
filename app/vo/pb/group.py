from typing import List, Optional
from pydantic import BaseModel, Field
from app.vo.pb.match import Match
from app.vo.pb.player import Player


class Group(BaseModel):
    group_id: int
    group_name: str
    group_size: Optional[int] = None
    match: list[Match]
    players: Optional[List[Player]] = Field(default_factory=list)
