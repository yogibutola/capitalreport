from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.vo.pb.player import Player
from app.vo.pb.tournament_team import TournamentTeam


class TournamentRegistration(BaseModel):
    """One player's registration intent for a tournament.

    For singles this is just the player. For doubles it also records the partner
    choice: a named partner (``partner_email``), an email invite for someone who
    is not on the platform yet (``partner_email`` set with ``partner_registered``
    False), or ``needs_partner`` when the player is looking for one.
    """

    firstName: str
    lastName: str
    email: str
    dupr_rating: Optional[float] = None

    needs_partner: bool = False
    partner_email: Optional[str] = None
    partner_name: Optional[str] = None
    partner_dupr: Optional[float] = None
    partner_registered: bool = Field(
        False, description="True when the partner has a platform account"
    )
    team_id: Optional[str] = Field(None, description="Set once the draw is generated")


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
    """A pool (group) that plays a round robin before the knockout stage.

    ``players`` is populated for singles tournaments, ``teams`` for doubles.
    """
    pool_id: int
    pool_name: str
    players: List[Player] = Field(default_factory=list)
    teams: List[TournamentTeam] = Field(default_factory=list)
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
    match_format: Literal["singles", "doubles"] = Field(
        "doubles", description="Format of the tournament: singles or doubles"
    )
    dupr_min: Optional[float] = Field(
        None, ge=0.0, le=8.0, description="Lowest DUPR rating allowed to register"
    )
    dupr_max: Optional[float] = Field(
        None, ge=0.0, le=8.0, description="Highest DUPR rating allowed to register"
    )
    pool_size: int = Field(4, gt=1, description="Target number of players per pool")
    advancers_per_pool: int = Field(2, gt=0, description="How many players advance from each pool to the knockout stage")
    tournament_status: Optional[str] = "pending"
    players: Optional[List[Player]] = Field(
        default_factory=list,
        description="Flat roster of every individual participant (registrants + partners)",
    )
    registrations: Optional[List[TournamentRegistration]] = Field(default_factory=list)
    teams: Optional[List[TournamentTeam]] = Field(
        default_factory=list, description="Doubles pairs, populated when the draw is generated"
    )
    pools: Optional[List[Pool]] = Field(default_factory=list)
    knockout: Optional[List[KnockoutRound]] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dupr_range(self):
        if (
            self.dupr_min is not None
            and self.dupr_max is not None
            and self.dupr_max < self.dupr_min
        ):
            raise ValueError("dupr_max must be greater than or equal to dupr_min")
        return self

    @property
    def player_emails(self) -> List[str]:
        """Get a list of all player emails registered for the tournament."""
        return [player.email for player in self.players]
