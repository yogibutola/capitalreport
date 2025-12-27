from fastapi import status, APIRouter, Depends

from app.store.mongo.pb_league_store import PBLeagueStore
from app.vo.pb.league import League
from app.services.pb_league_service import PBLeagueService
from app.vo.pb.match_details_payload import MatchDetailsPayload

router = APIRouter(tags=["League"])


def get_pb_league_service() -> PBLeagueService:
    """Dependency injector for PBLeagueService."""
    # Using PBMongoDBStore for league operations
    pb_league_store = PBLeagueStore()
    return PBLeagueService(pb_league_store)


@router.post("/league", status_code=status.HTTP_201_CREATED)
def create_league(league: League, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """Create a new league."""
    pb_league_service.save_league_details(league)
    return {"message": "League created successfully", "league_id": league.league_id}

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

@router.post("/league/round", status_code=status.HTTP_200_OK)
def update_league_with_round_details(league: League, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Update a league."""
    pb_league_service.update_league_with_round_details(league)
    return {"message": "League updated successfully"}

@router.get("/league/name/{league_name}", status_code=status.HTTP_200_OK)   
def get_league_details_by_league_name(league_name: str, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Get a league by name."""
    return pb_league_service.get_league_details_by_league_name(league_name) 

@router.post("/league/match/score", status_code=status.HTTP_200_OK)
def save_match_details(match_details: MatchDetailsPayload, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Save match details."""
    pb_league_service.save_match_details(match_details)
