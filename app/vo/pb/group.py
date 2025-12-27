from pydantic import BaseModel
from app.vo.pb.match import Match


class Group(BaseModel):
    group_id: str
    group_name: str
    match: list[Match]
