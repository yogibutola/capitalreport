from typing import List, Literal, Optional
from pydantic import BaseModel, Field

VoteOption = Literal["In", "In but late", "In but leave early", "May be", "Out"]


class GroupCreate(BaseModel):
    """Payload to create a new group."""
    name: str = Field(..., min_length=1, description="Group name")
    description: Optional[str] = Field(None, description="Optional description")
    creator_email: str = Field(..., description="Email of the player creating the group")


class GroupMemberAdd(BaseModel):
    """Payload to add a member to a group."""
    email: str = Field(..., description="Email of the player to add")


class GroupEventCreate(BaseModel):
    """Payload to create an event inside a group."""
    title: Optional[str] = Field(None, description="Event title (defaults to 'Group Session — <date>')")
    date: Optional[str] = Field(None, description="ISO date string; defaults to today")
    time: Optional[str] = Field(None, description="Event time, e.g. '18:30'")
    place: Optional[str] = Field(None, description="Where the event takes place")
    notes: Optional[str] = Field(None, description="Optional notes for the event")


class EventVoteCreate(BaseModel):
    """Payload to cast (or change) a player's vote on an event."""
    voter_email: str = Field(..., description="Email of the voting player")
    voter_name: str = Field(..., description="Display name of the voting player")
    vote: VoteOption = Field(..., description="One of: In, In but late, In but leave early, May be, Out")


class EventVoteResponse(BaseModel):
    """A player's vote on an event."""
    voter_email: str
    voter_name: str
    vote: str
    timestamp: str


class GroupMessage(BaseModel):
    """A discussion message at the group or event level."""
    author_email: str = Field(..., description="Email of the message author")
    author_name: str = Field(..., description="Display name of the author")
    content: str = Field(..., min_length=1, description="Message content")


class GroupMessageResponse(BaseModel):
    """Full message including metadata."""
    message_id: str
    author_email: str
    author_name: str
    content: str
    timestamp: str


class GroupEventResponse(BaseModel):
    """Full event document returned from API."""
    event_id: str
    title: str
    date: str
    time: Optional[str] = None
    place: Optional[str] = None
    notes: Optional[str] = None
    votes: List[EventVoteResponse] = Field(default_factory=list)
    messages: List[GroupMessageResponse] = Field(default_factory=list)


class GroupResponse(BaseModel):
    """Full group document returned from API."""
    group_id: str
    name: str
    description: Optional[str] = None
    creator_email: str
    members: List[str] = Field(default_factory=list)
    events: List[GroupEventResponse] = Field(default_factory=list)
    messages: List[GroupMessageResponse] = Field(default_factory=list)
    created_at: str
