from app.vo.pb.group import Group
from pydantic import BaseModel
class Round(BaseModel):
    round_id: int
    group: list[Group]
    