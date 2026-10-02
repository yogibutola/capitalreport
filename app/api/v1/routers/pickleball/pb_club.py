from typing import List

from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_current_admin, get_current_player
from app.services.pb_club_service import PBClubService
from app.store.mongo.pb_club_store import PBClubStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.club import ClubCreate, ClubResponse, ClubSessionResponse, ClubUpdate, VenueCreate, VenueResponse

router = APIRouter(tags=["Club"])


def get_pb_club_service() -> PBClubService:
    """Dependency injector for PBClubService."""
    return PBClubService(PBClubStore(), PBPlayerStore())


@router.post("/clubs", status_code=status.HTTP_201_CREATED, response_model=ClubSessionResponse)
def create_club(
    req: ClubCreate,
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_player),
):
    """Create a club run by the signed-in account (one club per person).

    Returns a fresh session token with the admin role - the caller's current
    token predates the club and still says "player"."""
    return service.create_club(payload["sub"], req)


@router.get("/clubs/me", response_model=ClubResponse)
def get_my_club(
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_admin),
):
    """The club the signed-in owner runs."""
    return service.get_club(payload["club_id"])


@router.put("/clubs/me", response_model=ClubResponse)
def update_my_club(
    req: ClubUpdate,
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_admin),
):
    """Edit the signed-in owner's club. Only the fields sent are changed."""
    return service.update_club(payload["club_id"], req)


@router.get("/clubs/me/venues", response_model=List[VenueResponse])
def list_my_venues(
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_admin),
):
    return service.list_venues(payload["club_id"])


@router.post("/clubs/me/venues", status_code=status.HTTP_201_CREATED, response_model=VenueResponse)
def add_venue(
    req: VenueCreate,
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_admin),
):
    return service.add_venue(payload["club_id"], req)


@router.put("/clubs/me/venues/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: str,
    req: VenueCreate,
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_admin),
):
    return service.update_venue(payload["club_id"], venue_id, req)


@router.delete("/clubs/me/venues/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_venue(
    venue_id: str,
    service: PBClubService = Depends(get_pb_club_service),
    payload: dict = Depends(get_current_admin),
):
    service.delete_venue(payload["club_id"], venue_id)
