from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_admin, get_current_player
from app.services.pb_tournament_service import PBTournamentService
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.response_model.tournament_response import TournamentResponse
from app.vo.pb.tournament import Tournament
from app.vo.pb.tournament_match_score_payload import TournamentMatchScorePayload
from app.vo.pb.tournament_registration_payload import TournamentRegistrationPayload

router = APIRouter(tags=["Tournament"])


def get_pb_tournament_service() -> PBTournamentService:
    """Dependency injector for PBTournamentService."""
    return PBTournamentService(PBTournamentStore())


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
    return pb_tournament_service.get_tournaments_by_club(payload.get("sub"))


@router.get("/player/tournaments/{email_id}", status_code=status.HTTP_200_OK)
def get_player_tournaments(
    email_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
):
    """Get the tournaments a player is registered for."""
    return pb_tournament_service.get_tournaments_by_player_email(email_id)


@router.get("/tournament/id/{tournament_id}", status_code=status.HTTP_200_OK)
def get_tournament_by_id(
    tournament_id: str,
    pb_tournament_service: PBTournamentService = Depends(get_pb_tournament_service),
):
    """Get a tournament (pools + knockout bracket) by id."""
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
    tournament.club_id = payload.get("sub")
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
    email invite, or looking-for-a-partner)."""
    email = payload.get("sub") or registration.email
    try:
        pb_tournament_service.register(registration.tournament_id, registration, email)
        return {"message": "Player registered successfully"}
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
    _: dict = Depends(get_current_admin),
):
    """Record a pool or knockout match result. Resolves pool qualifiers into the
    bracket and advances knockout winners (and byes). Returns the updated
    tournament. (Admin only)"""
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
    """Undo the draw and re-open registration. (Admin only)"""
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
    """Delete a tournament. (Admin only)"""
    try:
        success = pb_tournament_service.delete_tournament(tournament_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
        return {"message": "Tournament deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
