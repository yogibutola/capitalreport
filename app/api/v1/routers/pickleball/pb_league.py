from fastapi import status, APIRouter, Depends

from app.store.mongo.pb_league_store import PBLeagueStore
from app.vo.pb.league import League
from app.services.pb_league_service import PBLeagueService
from app.vo.pb.match_details_payload import MatchDetailsPayload
from app.vo.pb.slotting_details_payload import SlottingDetailsPayload
from app.vo.pb.league_registration_payload import LeagueRegistrationPayload
from app.api.v1.deps import get_current_admin, get_current_player
from fastapi import status, APIRouter, Depends, HTTPException

router = APIRouter(tags=["League"])


def get_pb_league_service() -> PBLeagueService:
    """Dependency injector for PBLeagueService."""
    # Using PBMongoDBStore for league operations
    pb_league_store = PBLeagueStore()
    return PBLeagueService(pb_league_store)


@router.get("/all_leagues", status_code=status.HTTP_200_OK)
def get_all_leagues(pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Get all leagues."""
    return pb_league_service.get_all_leagues()


@router.get("/league/{status}", status_code=status.HTTP_200_OK)
def get_league_by_status(status: str, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Get a league by status."""
    return pb_league_service.get_league_by_status(status)


@router.get("/league/id/{league_id}", status_code=status.HTTP_200_OK)
def get_players_by_league_id(league_id: str, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Get a league by id."""
    return pb_league_service.get_players_by_league_id(league_id)


@router.get("/league/name/{league_name}", status_code=status.HTTP_200_OK)
def get_league_details_by_league_name(league_name: str,
                                      pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Get a league by name."""
    return pb_league_service.get_league_details_by_league_name(league_name)


################################################### POST METHODS ###################################################

@router.post("/league", status_code=status.HTTP_201_CREATED)
def create_league(league: League, 
                  pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                  payload: dict = Depends(get_current_admin)):
    """Create a new league. (Admin only)"""
    pb_league_service.save_league_details(league)
    return {"message": "League created successfully", "league_id": league.league_id}


@router.post("/league/round", status_code=status.HTTP_200_OK)
def update_league_with_round_details(slotting_details: SlottingDetailsPayload,
                                     pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                                     payload: dict = Depends(get_current_admin)):
    """ Update a league. (Admin only)"""
    pb_league_service.update_league_with_round_details(slotting_details)
    return {"message": "League updated successfully"}


@router.post("/league/match/score", status_code=status.HTTP_200_OK)
def save_match_score(match_details: MatchDetailsPayload,
                       pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                       payload: dict = Depends(get_current_player)):
    """ Save match details. (Authenticated users)"""
    pb_league_service.save_match_score(match_details)


@router.post("/league/register", status_code=status.HTTP_200_OK)
def register_player_to_league(registration: LeagueRegistrationPayload,
                             pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                             payload: dict = Depends(get_current_player)):
    """Register a player for a league."""
    try:
        pb_league_service.register_player(registration.league_id, registration.email)
        return {"message": "Player registered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

