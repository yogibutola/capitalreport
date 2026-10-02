from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import (
    get_current_admin,
    get_current_player,
    get_optional_user_payload,
    require_club_owner,
    require_self,
)
from app.services.pb_tournament_service import AccountExistsError, PBTournamentService
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.response_model.tournament_response import TournamentResponse
from app.vo.pb.tournament import Tournament
from app.vo.pb.tournament_match_score_payload import TournamentMatchScorePayload
from app.vo.pb.tournament_registration_payload import (
    PublicTournamentRegistrationPayload,
    TournamentRegistrationPayload,
)

router = APIRouter(tags=["Tournament"])


def get_pb_tournament_service() -> PBTournamentService:
    """Dependency injector for PBTournamentService."""
    return PBTournamentService(PBTournamentStore())


def _require_tournament_owner(
    pb_tournament_service: PBTournamentService, tournament_id: str, payload: dict
) -> None:
    """404 for an unknown tournament, 403 unless the caller's club runs it."""
    owner = pb_tournament_service.get_tournament_owner(tournament_id)
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    require_club_owner(owner.get("club_id"), payload)


@router.get("/all_tournaments", status_code=status.HTTP_200_OK)
def get_all_tournaments(
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
):
    """Get all tournaments (public discovery, across all clubs)."""
    return pb_tournament_service.get_all_tournaments()


@router.get("/my_tournaments", status_code=status.HTTP_200_OK)
def get_my_tournaments(
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_admin),
):
    """Get the tournaments created by the authenticated admin's club. (Admin only)"""
    return pb_tournament_service.get_tournaments_by_club(payload["club_id"])


@router.get("/player/tournaments/{email_id}", status_code=status.HTTP_200_OK)
def get_player_tournaments(
    email_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_player),
):
    """Get the tournaments a player is registered for. (Own tournaments only)"""
    require_self(email_id, payload)
    return pb_tournament_service.get_tournaments_by_player_email(email_id)


@router.get("/tournament/id/{tournament_id}", status_code=status.HTTP_200_OK)
def get_tournament_by_id(
    tournament_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict | None = Depends(get_optional_user_payload),
):
    """Get a tournament (pools + knockout bracket) by id.

    Signed-in callers get the full tournament. Anonymous visitors - the public
    share link on a flyer - get the event details only, with no roster, teams
    or bracket, since those carry other players' emails."""
    if payload is None:
        public = pb_tournament_service.get_public_tournament(tournament_id)
        if not public:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
        return public
    tournament = pb_tournament_service.get_tournament_by_id(tournament_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return tournament


@router.post("/tournament", status_code=status.HTTP_201_CREATED, response_model=TournamentResponse)
def create_tournament(
    tournament: Tournament,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_admin),
):
    """Create a new tournament. Seeds players into round-robin pools and builds
    the knockout bracket. (Admin only)"""
    tournament.club_id = payload["club_id"]
    pb_tournament_service.create_tournament(tournament)
    return TournamentResponse(
        tournament_id=tournament.tournament_id, tournament_name=tournament.tournament_name
    )


@router.post("/tournament/register", status_code=status.HTTP_200_OK)
def register_player_to_tournament(
    registration: TournamentRegistrationPayload,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_player),
):
    """Register the authenticated player for a tournament.

    For doubles the payload also carries the partner choice (named partner,
    email invite, or looking-for-a-partner). The player is always the token's
    subject; any ``email`` in the body is ignored."""
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract email from token",
        )
    try:
        pb_tournament_service.register(registration.tournament_id, registration, email)
        return {"message": "Player registered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/tournament/register/public", status_code=status.HTTP_201_CREATED)
def register_new_player_to_tournament(
    registration: PublicTournamentRegistrationPayload,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
):
    """Public registration for a brand-new user, reached from the share link
    embedded on a tournament flyer / image.

    Creates the player account and registers it for the tournament in one step,
    returning a session token so the new player lands logged in. No auth required.
    """
    try:
        return pb_tournament_service.register_public(registration)
    except AccountExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/tournament/{tournament_id}/draw", status_code=status.HTTP_200_OK)
def generate_tournament_draw(
    tournament_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_admin),
):
    """Close registration and generate the pools + knockout bracket. (Admin only)

    Doubles registrations without a partner are auto-paired by DUPR rating."""
    _require_tournament_owner(pb_tournament_service, tournament_id, payload)
    try:
        return pb_tournament_service.generate_draw(tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/tournament/{tournament_id}/match/score", status_code=status.HTTP_200_OK)
def record_tournament_match_score(
    tournament_id: str,
    payload: TournamentMatchScorePayload,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    admin: dict = Depends(get_current_admin),
):
    """Record a pool or knockout match result. Resolves pool qualifiers into the
    bracket and advances knockout winners (and byes). Returns the updated
    tournament. (Admin only - the club that runs it)"""
    _require_tournament_owner(pb_tournament_service, tournament_id, admin)
    try:
        return pb_tournament_service.record_match_score(tournament_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/tournament/{tournament_id}/reopen", status_code=status.HTTP_200_OK)
def reopen_tournament_registration(
    tournament_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_admin),
):
    """Undo the draw and re-open registration. (Admin only - the club that runs it)"""
    _require_tournament_owner(pb_tournament_service, tournament_id, payload)
    try:
        pb_tournament_service.reopen_registration(tournament_id)
        return {"message": "Registration reopened"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/tournament/{tournament_id}/player", status_code=status.HTTP_200_OK)
def unregister_player_from_tournament(
    tournament_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_player),
):
    """Unregister the authenticated player from a tournament."""
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract email from token",
        )
    try:
        pb_tournament_service.unregister_player(tournament_id, email)
        return {"message": "Player unregistered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/tournament/{tournament_id}", status_code=status.HTTP_200_OK)
def delete_tournament(
    tournament_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
    payload: dict = Depends(get_current_admin),
):
    """Delete a tournament. (Admin only - the club that runs it)"""
    _require_tournament_owner(pb_tournament_service, tournament_id, payload)
    try:
        success = pb_tournament_service.delete_tournament(tournament_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
        return {"message": "Tournament deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
