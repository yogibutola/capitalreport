from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.utils.security import verify_token

# Define the scheme. The tokenUrl should point to your login endpoint.
# Since we have a custom login structure, we just point to it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/signin")


def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validate the token and return the payload.
    This serves as the base dependency for both player and admin authentication.
    """
    return verify_token(token)


def get_current_player(payload: dict = Depends(get_current_user_payload)) -> dict:
    """
    Dependency to ensure the user is authenticated (valid token).
    Any valid user (player or admin) can access player endpoints.
    """
    return payload


def get_current_admin(payload: dict = Depends(get_current_user_payload)) -> dict:
    """
    Dependency to ensure the user is an admin.
    """
    role = payload.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return payload
