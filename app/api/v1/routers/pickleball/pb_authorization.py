from fastapi import status, APIRouter, Depends, HTTPException

from app.api.v1.deps import get_current_player
from app.services.pb_player_service import PBPlayerService

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import (
    PlayerSignup,
    PlayerResponse,
    PlayerLogin,
    ClubSignup,
    ChangePasswordRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)

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


@router.get("/profile", status_code=status.HTTP_200_OK, response_model=ProfileResponse)
def get_profile(
        payload: dict = Depends(get_current_player),
        pb_player_service: PBPlayerService = Depends(get_pb_player_service)
):
    """Return the authenticated user's profile."""
    try:
        return pb_player_service.get_profile(payload.get("sub"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load profile: {str(e)}"
        )


@router.put("/profile", status_code=status.HTTP_200_OK, response_model=ProfileResponse)
def update_profile(
        req: ProfileUpdateRequest,
        payload: dict = Depends(get_current_player),
        pb_player_service: PBPlayerService = Depends(get_pb_player_service)
):
    """
    Update the authenticated user's profile (name, age, email, DUPR rating, state, city).

    Raises:
        HTTPException 400: If a required name field is blanked out
        HTTPException 401: If the token is missing or invalid
        HTTPException 409: If the new email is already in use
        HTTPException 422: If a field fails validation
    """
    try:
        return pb_player_service.update_profile(payload.get("sub"), req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
        req: ChangePasswordRequest,
        payload: dict = Depends(get_current_player),
        pb_player_service: PBPlayerService = Depends(get_pb_player_service)
):
    """
    Change the authenticated user's password.

    Raises:
        HTTPException 400: If the current password is wrong or unchanged
        HTTPException 401: If the token is missing or invalid
        HTTPException 422: If the new password fails complexity rules
    """
    try:
        pb_player_service.change_password(payload.get("sub"), req)
        return {"message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )
