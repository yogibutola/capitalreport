from typing import Literal

from pydantic import BaseModel, Field


class TournamentMatchScorePayload(BaseModel):
    """Payload for recording a single tournament match result.

    ``stage`` says which structure the ``match_id`` lives in — a round-robin
    ``pool`` match or a ``knockout`` bracket match. The service advances the
    bracket (pool qualifiers, knockout winners, byes) after saving.
    """

    match_id: str = Field(..., description="ID of the pool or knockout match")
    stage: Literal["pool", "knockout"] = Field(..., description="Where the match lives")
    score_one: int = Field(..., ge=0, description="Points scored by participant one")
    score_two: int = Field(..., ge=0, description="Points scored by participant two")
