from typing import List
from fastapi import status, APIRouter, Depends, HTTPException

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import PlayerSignup, PlayerResponse, PlayerLogin
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
