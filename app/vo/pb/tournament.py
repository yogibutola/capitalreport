from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.vo.pb.player import Player


class PoolMatch(BaseModel):
    """A single round-robin match inside a pool."""
    match_id: str
    pool_id: int
    participant_one_email: Optional[str] = None
    participant_one_name: Optional[str] = None
    participant_two_email: Optional[str] = None
    participant_two_name: Optional[str] = None
    score_one: int = 0
    score_two: int = 0
    match_status: str = "YetToPlay"


class Pool(BaseModel):
    """A pool (group) that plays a round robin before the knockout stage."""
    pool_id: int
    pool_name: str
    players: List[Player] = Field(default_factory=list)
    matches: List[PoolMatch] = Field(default_factory=list)


class KnockoutMatch(BaseModel):
    """A single knockout-bracket match.

    Slots are described by label (e.g. "1st Pool A", "Winner R1 M2") until the
    pool stage resolves and real participants are filled in.
    """
    match_id: str
    slot_one_label: str
    slot_two_label: str
    participant_one_email: Optional[str] = None
    participant_one_name: Optional[str] = None
    participant_two_email: Optional[str] = None
    participant_two_name: Optional[str] = None
    score_one: int = 0
    score_two: int = 0
    match_status: str = "YetToPlay"


class KnockoutRound(BaseModel):
    round_id: int
    round_name: str
    matches: List[KnockoutMatch] = Field(default_factory=list)


class Tournament(BaseModel):
    tournament_id: Optional[str] = None
    club_id: Optional[str] = Field(None, description="Email of the admin/club that owns this tournament")
    club_name: Optional[str] = Field(None, description="Display name of the club that runs this tournament")
    location: Optional[str] = Field(None, description="Where the tournament is played (venue / club address)")

    @field_validator("tournament_id", mode="before")
    @classmethod
    def check_tournament_id(cls, v):
        if v == 0 or v == "0":
            return None
        return v

    tournament_name: str = Field(..., min_length=3, description="Name of the tournament")
    tournament_description: Optional[str] = None
    tournament_start_date: str = Field(
        ...,
        pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-\d{4}$",
        description="Start date in mm-dd-yyyy format",
    )
    tournament_end_date: Optional[str] = None
    match_format: str = Field("doubles", min_length=1, description="Format of the match, e.g. singles / doubles")
    pool_size: int = Field(4, gt=1, description="Target number of players per pool")
    advancers_per_pool: int = Field(2, gt=0, description="How many players advance from each pool to the knockout stage")
    tournament_status: Optional[str] = "pending"
    players: Optional[List[Player]] = Field(default_factory=list)
    pools: Optional[List[Pool]] = Field(default_factory=list)
    knockout: Optional[List[KnockoutRound]] = Field(default_factory=list)

    @property
    def player_emails(self) -> List[str]:
        """Get a list of all player emails registered for the tournament."""
        return [player.email for player in self.players]
