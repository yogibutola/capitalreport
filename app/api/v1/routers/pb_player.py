from fastapi import status, APIRouter, Depends, HTTPException

from app.vo.pb.player import PlayerSignup, PlayerResponse
from app.services.pb_player_service import PBPlayerService
from app.store.pb_mongo_db_store import PBMongoDBStore

router = APIRouter(tags=["Player"])


def get_pb_player_service() -> PBPlayerService:
    """Dependency injector for PBPlayerService."""
    mongo_store = PBMongoDBStore()
    return PBPlayerService(mongo_store)


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=PlayerResponse)
def signup_player(
    player_signup: PlayerSignup,
    pb_player_service: PBPlayerService = Depends(get_pb_player_service)
):
    """
    Register a new player.
    
    Args:
        player_signup: Player signup data (firstName, lastName, email, password, dupr_rating)
        
    Returns:
        PlayerResponse: Created player data (without password)
        
    Raises:
        HTTPException 409: If email already exists
        HTTPException 422: If validation fails
    """
    try:
        player_response = pb_player_service.register_player(player_signup)
        return player_response
    except HTTPException:
        # Re-raise HTTPExceptions (like 409 Conflict)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create player: {str(e)}"
        )
