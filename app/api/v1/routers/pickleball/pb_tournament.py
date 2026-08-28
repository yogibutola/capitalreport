from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_admin
from app.services.pb_tournament_service import PBTournamentService
from app.store.mongo.pb_tournament_store import PBTournamentStore
from app.vo.pb.response_model.tournament_response import TournamentResponse
from app.vo.pb.tournament import Tournament

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
