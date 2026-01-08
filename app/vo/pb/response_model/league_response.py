from pydantic import BaseModel, field_validator
import re


class LeagueResponse(BaseModel):
    league_id: str
    league_name: str

    @field_validator('league_id', mode='before')
    @classmethod
    def normalize_object_id(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            return str(v)
        # Handle "ObjectId('...')" format
        match = re.search(r"ObjectId\(['\"]?([a-f0-9]{24})['\"]?\)", v)
        if match:
            return match.group(1)
        return v
    