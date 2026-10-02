from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from app.utils.security import verify_token

# Define the scheme. The tokenUrl should point to your login endpoint.
# Since we have a custom login structure, we just point to it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/signin")
# Same scheme for endpoints that also serve anonymous callers: no token -> None.
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/signin", auto_error=False)

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


def get_current_superadmin(
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> dict:
    """
    Dependency to ensure the user is the application ("platform") admin.

    The superadmin role is granted at sign-in to emails in the
    ``SUPERADMIN_EMAILS`` allowlist - it is distinct from a club (``role="admin"``).
    """
    if payload.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin privileges required"
        )
    _reject_demo_writes(payload, request)
    return payload


def get_optional_user_payload(token: str | None = Depends(optional_oauth2_scheme)) -> dict | None:
    """
    Token payload when the caller sent a valid token, else None.

    For endpoints that also serve anonymous visitors (e.g. a tournament's public
    share link) and return less to them. A bad or expired token is treated as
    anonymous rather than a 401, so a stale session can still open the page.
    """
    if not token:
        return None
    try:
        return verify_token(token)
    except HTTPException:
        return None


def require_self(email: str | None, payload: dict) -> None:
    """
    403 unless ``email`` is the caller's own account.

    For endpoints keyed by a player's email in the path: a player may read only
    their own data. The platform admin (superadmin) may read anyone's.
    """
    if payload.get("role") == "superadmin":
        return
    if not email or email.strip().lower() != (payload.get("sub") or "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data",
        )


def is_club_owner(club_id: str | None, payload: dict) -> bool:
    """
    True when the caller is the club that owns a league/tournament.

    Leagues and tournaments store their owning club's email as ``club_id``
    (taken from the creating admin's token), so ownership is that email matching
    the caller's ``sub``. A resource with no ``club_id`` belongs to nobody.
    """
    caller = (payload.get("sub") or "").lower()
    return payload.get("role") == "admin" and bool(club_id) and club_id.lower() == caller


def require_club_owner(club_id: str | None, payload: dict) -> None:
    """403 unless the caller is the club that owns the resource (see ``is_club_owner``)."""
    if not is_club_owner(club_id, payload):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the club that runs this can change it",
        )
