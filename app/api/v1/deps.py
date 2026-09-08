from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from app.utils.security import verify_token

# Define the scheme. The tokenUrl should point to your login endpoint.
# Since we have a custom login structure, we just point to it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/signin")

# HTTP methods that only read state - demo sessions are allowed these.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validate the token and return the payload.
    This serves as the base dependency for both player and admin authentication.
    """
    return verify_token(token)


def _reject_demo_writes(payload: dict, request: Request) -> None:
    """
    Demo tokens (issued by /api/v1/demo-signin) carry a "demo" claim. The demo
    is read-only, so block anything that isn't a safe/read method.
    """
    if payload.get("demo") and request.method not in _SAFE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is a read-only demo. Sign up to make changes.",
        )


def get_current_player(
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> dict:
    """
    Dependency to ensure the user is authenticated (valid token).
    Any valid user (player or admin) can access player endpoints.
    """
    _reject_demo_writes(payload, request)
    return payload


def get_current_admin(
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> dict:
    """
    Dependency to ensure the user is an admin.
    """
    role = payload.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    _reject_demo_writes(payload, request)
    return payload
