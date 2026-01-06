from fastapi import status, APIRouter, Depends, HTTPException

from app.services.pb_player_service import PBPlayerService

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import PlayerSignup, PlayerResponse, PlayerLogin, ClubSignup

router = APIRouter(tags=["Authorization"])


def get_pb_player_service() -> PBPlayerService:
    """Dependency injector for PBPlayerService."""
    pb_player_store = PBPlayerStore()
    return PBPlayerService(pb_player_store)


@router.post("/signup/club", status_code=status.HTTP_201_CREATED, response_model=PlayerResponse)
def signup_club(
        club_signup: ClubSignup,
        pb_player_service: PBPlayerService = Depends(get_pb_player_service)
):
    """
    Register a new club (admin).

    Args:
        club_signup: Club signup data (clubName, email, password, address, phone)

    Returns:
        PlayerResponse: Created admin data
    """
    try:
        return pb_player_service.register_club(club_signup)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create club: {str(e)}"
        )


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


@router.post("/signin", status_code=status.HTTP_200_OK, response_model=PlayerResponse)
def signin_player(
        login_data: PlayerLogin,
        pb_player_service: PBPlayerService = Depends(get_pb_player_service)
):
    """
    Authenticate a player.

    Args:
        login_data: Player login data (email, password)

    Returns:
        PlayerResponse: Authenticated player data

    Raises:
        HTTPException 401: If authentication fails
    """
    try:
        return pb_player_service.signin_player(login_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sign in: {str(e)}"
        )
