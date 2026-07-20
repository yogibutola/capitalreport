from datetime import datetime, timezone
from typing import List

from fastapi import status, APIRouter, Depends, HTTPException

from app.store.mongo.pb_group_store import PBGroupStore
from app.vo.pb.group_ext import (
    GroupCreate,
    GroupMemberAdd,
    GroupEventCreate,
    GroupMessage,
    GroupResponse,
    GroupEventResponse,
    GroupMessageResponse,
    EventVoteCreate,
    EventVoteResponse,
)

router = APIRouter(tags=["Groups"])


def get_group_store() -> PBGroupStore:
    return PBGroupStore()


def _doc_to_response(doc: dict) -> GroupResponse:
    """Convert a raw MongoDB group document to GroupResponse."""

    def msg_to_resp(m: dict) -> GroupMessageResponse:
        return GroupMessageResponse(
            message_id=m.get("message_id", ""),
            author_email=m.get("author_email", ""),
            author_name=m.get("author_name", ""),
            content=m.get("content", ""),
            timestamp=m.get("timestamp", ""),
        )

    def vote_to_resp(v: dict) -> EventVoteResponse:
        return EventVoteResponse(
            voter_email=v.get("voter_email", ""),
            voter_name=v.get("voter_name", ""),
            vote=v.get("vote", ""),
            timestamp=v.get("timestamp", ""),
        )

    def event_to_resp(e: dict) -> GroupEventResponse:
        return GroupEventResponse(
            event_id=e.get("event_id", ""),
            title=e.get("title", ""),
            date=e.get("date", ""),
            time=e.get("time"),
            place=e.get("place"),
            notes=e.get("notes"),
            votes=[vote_to_resp(v) for v in e.get("votes", [])],
            messages=[msg_to_resp(m) for m in e.get("messages", [])],
        )

    return GroupResponse(
        group_id=doc.get("group_id", ""),
        name=doc.get("name", ""),
        description=doc.get("description"),
        creator_email=doc.get("creator_email", ""),
        members=doc.get("members", []),
        events=[event_to_resp(e) for e in doc.get("events", [])],
        messages=[msg_to_resp(m) for m in doc.get("messages", [])],
        created_at=doc.get("created_at", ""),
    )


# ─────────────────────────────────────────────────────────────
# Group CRUD
# ─────────────────────────────────────────────────────────────

@router.post("/groups", status_code=status.HTTP_201_CREATED, response_model=GroupResponse)
def create_group(
    payload: GroupCreate,
    store: PBGroupStore = Depends(get_group_store),
):
    """Create a new player group."""
    try:
        doc = store.create_group(
            name=payload.name,
            description=payload.description,
            creator_email=payload.creator_email,
        )
        return _doc_to_response(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create group: {e}")


@router.get("/groups/player/{email}", response_model=List[GroupResponse])
def get_groups_for_player(
    email: str,
    store: PBGroupStore = Depends(get_group_store),
):
    """Get all groups a player belongs to."""
    try:
        docs = store.get_groups_for_player(email)
        return [_doc_to_response(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch groups: {e}")


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: str,
    store: PBGroupStore = Depends(get_group_store),
):
    """Get full group details (events + messages)."""
    doc = store.get_group_by_id(group_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Group not found")
    return _doc_to_response(doc)


# ─────────────────────────────────────────────────────────────
# Members
# ─────────────────────────────────────────────────────────────

@router.post("/groups/{group_id}/members", status_code=status.HTTP_200_OK)
def add_member(
    group_id: str,
    payload: GroupMemberAdd,
    store: PBGroupStore = Depends(get_group_store),
):
    """Add a player to a group."""
    found = store.add_member(group_id, payload.email)
    if not found:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"message": f"Player {payload.email} added to group"}


# ─────────────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────────────

@router.post("/groups/{group_id}/events", status_code=status.HTTP_201_CREATED, response_model=GroupEventResponse)
def add_event(
    group_id: str,
    payload: GroupEventCreate,
    store: PBGroupStore = Depends(get_group_store),
):
    """Add an event to a group. Date/title default to today when omitted."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_str = payload.date or today
    title = payload.title or f"Group Session — {datetime.now(timezone.utc).strftime('%b %d, %Y')}"

    event = store.add_event(
        group_id,
        title=title,
        date=date_str,
        time=payload.time,
        place=payload.place,
        notes=payload.notes,
    )
    if not event:
        raise HTTPException(status_code=404, detail="Group not found")

    return GroupEventResponse(
        event_id=event["event_id"],
        title=event["title"],
        date=event["date"],
        time=event.get("time"),
        place=event.get("place"),
        notes=event.get("notes"),
        votes=[],
        messages=[],
    )


@router.post("/groups/{group_id}/events/{event_id}/vote", status_code=status.HTTP_200_OK, response_model=EventVoteResponse)
def vote_on_event(
    group_id: str,
    event_id: str,
    payload: EventVoteCreate,
    store: PBGroupStore = Depends(get_group_store),
):
    """Cast or change a player's attendance vote on an event."""
    vote = store.set_event_vote(
        group_id=group_id,
        event_id=event_id,
        voter_email=payload.voter_email,
        voter_name=payload.voter_name,
        vote=payload.vote,
    )
    if not vote:
        raise HTTPException(status_code=404, detail="Group or event not found")
    return EventVoteResponse(**vote)


# ─────────────────────────────────────────────────────────────
# Discussions
# ─────────────────────────────────────────────────────────────

@router.post("/groups/{group_id}/messages", status_code=status.HTTP_201_CREATED, response_model=GroupMessageResponse)
def post_group_message(
    group_id: str,
    payload: GroupMessage,
    store: PBGroupStore = Depends(get_group_store),
):
    """Post a message to the group-level discussion."""
    msg = store.add_group_message(
        group_id=group_id,
        author_email=payload.author_email,
        author_name=payload.author_name,
        content=payload.content,
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Group not found")
    return GroupMessageResponse(**msg)


@router.post("/groups/{group_id}/events/{event_id}/messages", status_code=status.HTTP_201_CREATED, response_model=GroupMessageResponse)
def post_event_message(
    group_id: str,
    event_id: str,
    payload: GroupMessage,
    store: PBGroupStore = Depends(get_group_store),
):
    """Post a message to a specific event's discussion thread."""
    msg = store.add_event_message(
        group_id=group_id,
        event_id=event_id,
        author_email=payload.author_email,
        author_name=payload.author_name,
        content=payload.content,
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Group or event not found")
    return GroupMessageResponse(**msg)
