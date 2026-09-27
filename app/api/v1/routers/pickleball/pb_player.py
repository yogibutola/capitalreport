from typing import List, Optional
from fastapi import status, APIRouter, Depends, HTTPException, Query

from app.api.v1.deps import get_current_player
from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import PlayerSignup, PlayerResponse, PlayerLogin, PlayerSearchResponse
from app.services.pb_player_service import PBPlayerService

router = APIRouter(tags=["Player"])


def get_pb_player_service() -> PBPlayerService:
    """Dependency injector for PBPlayerService."""
    pb_player_store = PBPlayerStore()
    return PBPlayerService(pb_player_store)


@router.get("/players", response_model=List[PlayerResponse])
def get_players(pb_player_service: PBPlayerService = Depends(get_pb_player_service)):
    """
    Get a list of all players.
    
    Returns:
        List[PlayerResponse]: List of players
    """
    try:
            return pb_player_service.get_all_players()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch players: {str(e)}"
        )

@router.get("/players/search", response_model=PlayerSearchResponse)
def search_players(
        first_name: Optional[str] = Query(None, max_length=100, description="Case-insensitive substring"),
        last_name: Optional[str] = Query(None, max_length=100, description="Case-insensitive substring"),
        dupr_min: Optional[float] = Query(None, ge=0.0, le=8.0),
        dupr_max: Optional[float] = Query(None, ge=0.0, le=8.0),
        radius_miles: Optional[float] = Query(None, gt=0, le=500, description="Only players this close"),
        origin_zip: Optional[str] = Query(None, max_length=10, description="Measure from here instead of the profile ZIP"),
        limit: int = Query(200, ge=1, le=500),
        current_player: dict = Depends(get_current_player),
        pb_player_service: PBPlayerService = Depends(get_pb_player_service),
):
    """Find other players by name, DUPR band and/or distance.

    Declared BEFORE ``/players/{league_id}``: FastAPI matches in declaration
    order, so the reverse would parse every search as ``league_id="search"``.

    Deliberately no ``except Exception`` wrapper - ``HTTPException`` is an
    ``Exception``, so catching it would rewrite the service's 400s as 500s and
    the frontend would lose the error codes it branches on.
    """
    return pb_player_service.search_players(
        searcher_email=current_player.get("sub"),
        first_name=first_name,
        last_name=last_name,
        dupr_min=dupr_min,
        dupr_max=dupr_max,
        radius_miles=radius_miles,
        origin_zip=origin_zip,
        limit=limit,
    )


@router.get("/players/{league_id}", response_model=PlayerResponse)
def get_player_by_league_id(league_id: str, pb_player_service: PBPlayerService = Depends(get_pb_player_service)):
    """
    Get a player by league id.
    
    Args:
        league_id: League id
    
    Returns:
        PlayerResponse: Player data
    """
    try:
        return pb_player_service.get_player_by_league_id(league_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch player by league id: {str(e)}"
        )   

@router.get("/player/league/{email_id}", status_code=status.HTTP_200_OK)
def get_league_by_player_email(email_id: str, pb_player_service: PBPlayerService = Depends(get_pb_player_service)):
    """ Get a player by email."""
    return pb_player_service.get_league_by_player_email(email_id)   
    