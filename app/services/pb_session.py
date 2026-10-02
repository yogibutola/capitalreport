"""What a session token says about the account behind it.

One place decides the role and claims for every way a token is minted (sign-in,
signup, demo sign-in, email change, club creation), so they can't drift:

  * ``superadmin`` - the email is in ``SUPERADMIN_EMAILS`` (platform admin)
  * ``admin``      - the account owns a club; the token also carries ``club_id``
  * ``player``     - everyone else

Stored documents carry no role: it is derived here every time.
"""
from app.utils.security import create_access_token, is_superadmin_email


def session_claims(player: dict, club: dict | None, demo: bool = False) -> dict:
    claims = {"sub": player["email"].lower(), "pid": str(player["_id"])}
    if club:
        claims["club_id"] = str(club["_id"])
    if is_superadmin_email(player["email"]):
        claims["role"] = "superadmin"
    elif club:
        claims["role"] = "admin"
    else:
        claims["role"] = "player"
    if demo:
        claims["demo"] = True
    return claims


def issue_session(player: dict, club: dict | None, demo: bool = False) -> tuple[str, dict]:
    """``(token, claims)`` for ``player``; ``club`` is the club they own, if any."""
    claims = session_claims(player, club, demo)
    return create_access_token(data=claims), claims
