"""Hidden application-admin ("platform") console API.

Mounted under ``/api/v1/platform-console`` and excluded from the OpenAPI schema
(``include_in_schema=False``). Every route requires the superadmin role, which is
granted at sign-in to emails in the ``SUPERADMIN_EMAILS`` allowlist.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_superadmin
from app.services.pb_platform_service import PBPlatformService
from app.store.mongo.pb_audit_store import PBAuditStore
from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.player import ClubSignup, PlayerSignup

router = APIRouter(
    prefix="/platform-console",
    tags=["Platform Admin"],
    include_in_schema=False,
)


def get_platform_service() -> PBPlatformService:
    return PBPlatformService(
        PBPlayerStore(), PBLeagueStore(), PBTournamentStore(), PBAuditStore()
    )


@router.get("/clubs")
def list_clubs(
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    return svc.list_clubs()


@router.post("/clubs", status_code=status.HTTP_201_CREATED)
def create_club(
    payload: ClubSignup,
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    try:
        return svc.create_club(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create club: {e}")


@router.delete("/clubs/{club_id}")
def delete_club(
    club_id: str,
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    """Remove a club. Its owner keeps their player account."""
    svc.delete_club(club_id)
    return {"message": "Club removed", "id": club_id}


@router.get("/players")
def list_players(
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    return svc.list_players()


@router.post("/players", status_code=status.HTTP_201_CREATED)
def create_player(
    payload: PlayerSignup,
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    try:
        return svc.create_player(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create player: {e}")


@router.delete("/players/{email}")
def delete_player(
    email: str,
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    result = svc.delete_player(email)
    return {"message": "Player removed", **result}


@router.get("/activity")
def get_activity(
    actor: str | None = Query(None),
    action: str | None = Query(None),
    since: datetime | None = Query(None, description="ISO-8601 lower bound on ts"),
    limit: int = Query(200, ge=1, le=1000),
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    return svc.activity(actor=actor, action=action, since=since, limit=limit)


@router.get("/metrics")
def get_metrics(
    _: dict = Depends(get_current_superadmin),
    svc: PBPlatformService = Depends(get_platform_service),
):
    return svc.metrics()
