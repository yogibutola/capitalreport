from typing import List, Optional

from pydantic import BaseModel, Field

from app.vo.pb.round import Round


class SlottingDetailsPayload(BaseModel):
    league_id: Optional[str] = None
    league_name: str
    rounds: List[Round] = Field(default_factory=list)
