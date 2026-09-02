from typing import Optional

from pydantic import BaseModel, Field


class TournamentTeam(BaseModel):
    """A doubles pairing that is seeded into the pools / knockout bracket.

    Distinct from ``app.vo.pb.team.Team`` (which nests full ``Player`` objects and
    is used by league matches). Here we only keep what pool seeding and the
    bracket view need.
    """

    team_id: str
    team_name: str = Field(..., description='Display name, e.g. "Smith / Jones"')
    player_one_email: str
    player_one_name: str
    player_two_email: Optional[str] = None
    player_two_name: Optional[str] = None
    dupr_rating: float = Field(0.0, description="Average DUPR of the pair, used for seeding")
    formed_by: str = Field(
        "partner",
        description='How the team was formed: "partner" | "invite" | "auto"',
    )
