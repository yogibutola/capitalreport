from fastapi import status, APIRouter, Depends, HTTPException

from app.store.mongo.pb_league_store import PBLeagueStore
from app.vo.pb.league import League
from app.services.pb_league_service import PBLeagueService
from app.vo.pb.match import Match
from app.vo.pb.match_details_payload import MatchDetailsPayload
from app.vo.pb.response_model.league_response import LeagueResponse
from app.vo.pb.slotting_details_payload import SlottingDetailsPayload
from app.vo.pb.league_registration_payload import LeagueRegistrationPayload
from app.vo.pb.withdrawal_payload import WithdrawalPayload
from app.api.v1.deps import (
    get_current_admin,
    get_current_player,
    is_club_owner,
    require_club_owner,
    require_self,
)

router = APIRouter(tags=["League"])


def get_pb_league_service() -> PBLeagueService:
    """Dependency injector for PBLeagueService."""
    # Using PBMongoDBStore for league operations
    pb_league_store = PBLeagueStore()
    return PBLeagueService(pb_league_store)


def _require_league_owner(pb_league_service: PBLeagueService, league_id: str, payload: dict) -> dict:
    """404 for an unknown league, 403 unless the caller's club runs it."""
    owner = pb_league_service.get_league_owner(league_id)
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    require_club_owner(owner.get("club_id"), payload)
    return owner


@router.get("/all_leagues", status_code=status.HTTP_200_OK)
def get_all_leagues(pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """ Get all leagues (public discovery, across all clubs)."""
    return pb_league_service.get_all_leagues()


@router.get("/my_leagues", status_code=status.HTTP_200_OK)
def get_my_leagues(pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                   payload: dict = Depends(get_current_admin)):
    """ Get the leagues created by the authenticated admin's club. (Admin only)"""
    club_id = payload.get("sub")
    return pb_league_service.get_leagues_by_club(club_id)


# The league read endpoints below return rosters (emails + DUPR), so they need a
# signed-in caller. `/all_leagues` stays public: it carries no player data.

@router.get("/league/{status}", status_code=status.HTTP_200_OK)
def get_league_by_status(status: str, pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                         _: dict = Depends(get_current_player)):
    """ Get a league by status."""
    return pb_league_service.get_league_by_status(status)


@router.get("/league/id/{league_id}", status_code=status.HTTP_200_OK)
def get_players_by_league_id(league_id: str, pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                             _: dict = Depends(get_current_player)):
    """ Get a league by id."""
    return pb_league_service.get_players_by_league_id(league_id)


@router.get("/league/name/{league_name}", status_code=status.HTTP_200_OK)
def get_league_details_by_league_name(league_name: str,
                                      pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                                      _: dict = Depends(get_current_player)):
    """ Get a league by name."""
    return pb_league_service.get_league_details_by_league_name(league_name)


@router.get("/player/{email_id}/matches", status_code=status.HTTP_200_OK)
def get_matches_by_player_email(email_id: str,
                                pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                                payload: dict = Depends(get_current_player)):
    """ Get all matches for a player across all leagues and tournaments. (Own matches only)"""
    require_self(email_id, payload)
    return pb_league_service.get_matches_by_player_email(email_id)


################################################### POST METHODS ###################################################

@router.post("/league", status_code=status.HTTP_201_CREATED, response_model=LeagueResponse)
def create_league(league: League,
                  pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                  payload: dict = Depends(get_current_admin)):
    """Create a new league. (Admin only)"""
    league.club_id = payload.get("sub")
    pb_league_service.save_league_details(league)
    league_response = LeagueResponse(league_id=league.league_id, league_name=league.league_name)
    return league_response


@router.post("/league/round", status_code=status.HTTP_200_OK)
def update_league_with_round_details(slotting_details: SlottingDetailsPayload,
                                     pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                                     payload: dict = Depends(get_current_admin)):
    """ Update a league. (Admin only - the club that runs it)"""
    if not slotting_details.league_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="league_id is required")
    _require_league_owner(pb_league_service, slotting_details.league_id, payload)
    # Each match carries its own league_id and is upserted under it, so a payload
    # for an owned league must not smuggle in matches for someone else's.
    for round_item in slotting_details.rounds:
        for group_item in round_item.group:
            for match_item in group_item.match:
                if match_item.league_id != slotting_details.league_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail="Every match must belong to this league")
    pb_league_service.update_league_with_round_details(slotting_details)
    return {"message": "League updated successfully"}


@router.post("/league/match/score", status_code=status.HTTP_200_OK)
def save_match_score(match_details: MatchDetailsPayload,
                       pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                       payload: dict = Depends(get_current_player)):
    """ Save match details. (The match's players, or the club that runs the league)"""
    participants = pb_league_service.get_match_participant_emails(match_details.league_id, match_details.match_id)
    if participants is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    caller = (payload.get("sub") or "").lower()
    if caller not in participants:
        owner = pb_league_service.get_league_owner(match_details.league_id) or {}
        if not is_club_owner(owner.get("club_id"), payload):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the match's players or the league's club can record this score")
    pb_league_service.save_match_score(match_details)


@router.post("/league/register", status_code=status.HTTP_200_OK)
def register_player_to_league(registration: LeagueRegistrationPayload,
                             pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                             payload: dict = Depends(get_current_player)):
    """Register the authenticated player for a league.

    The player is always the token's subject; any ``email`` in the body is
    ignored, so one account can't sign another up."""
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not extract email from token")
    try:
        pb_league_service.register_player(registration.league_id, email)
        return {"message": "Player registered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/league/withdraw", status_code=status.HTTP_200_OK)
def withdraw_from_league(withdrawal: WithdrawalPayload,
                         pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                         payload: dict = Depends(get_current_player)):
    """Withdraw a player from a specific play day."""
    try:
        # Assuming the email is extracted from the JWT payload
        email = payload.get("sub") or withdrawal.email # Fallback if we added email to payload
        # But wait, withdrawal payload doesn't have email in the plan. Let's make sure email comes from payload.
        # Actually in other endpoints they extract from token or we can just expect it.
        # The PlayerLogin uses sub. But let's check `get_current_user_payload` -> returns `payload` which has `sub` (email usually).
        email = payload.get("sub")
        if not email:
            raise ValueError("Could not extract email from token")
            
        pb_league_service.withdraw_player(withdrawal.league_id, email, withdrawal.play_day, withdrawal.reason)
        return {"message": "Player withdrawn successfully for the play day"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/league/{league_id}/day/{play_day}/slot", status_code=status.HTTP_200_OK)
def slot_first_round_of_day(league_id: str, play_day: int,
                            pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                            payload: dict = Depends(get_current_admin)):
    """Admin endpoint to manually trigger slotting for the first round of a specific play day."""
    _require_league_owner(pb_league_service, league_id, payload)
    try:
        pb_league_service.slot_first_round_of_day(league_id, play_day)
        return {"message": f"First round matches slotted successfully for Play Day {play_day}"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/league/{league_id}/player", status_code=status.HTTP_200_OK)
def unregister_player_from_league(league_id: str,
                                   pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                                   payload: dict = Depends(get_current_player)):
    """Unregister the authenticated player from a league."""
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not extract email from token")
    try:
        pb_league_service.unregister_player(league_id, email)
        return {"message": "Player unregistered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unregister failed: {type(e).__name__}: {e}")


@router.delete("/league/{league_id}", status_code=status.HTTP_200_OK)
def delete_league(league_id: str,
                  pb_league_service: PBLeagueService = Depends(get_pb_league_service),
                  payload: dict = Depends(get_current_admin)):
    """Delete a league and its associated matches. (Admin only - the club that runs it)"""
    _require_league_owner(pb_league_service, league_id, payload)
    try:
        success = pb_league_service.delete_league(league_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        return {"message": "League deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
