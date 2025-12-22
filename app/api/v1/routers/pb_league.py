from fastapi import status, Query, APIRouter, Depends, HTTPException

from app.vo.pb.league import League
from app.services.pb_league_service import PBLeagueService
from app.store.pb_mongo_db_store import PBMongoDBStore

router = APIRouter(tags=["League"])


def get_pb_league_service() -> PBLeagueService:
    """Dependency injector for PBLeagueService."""
    # Using PBMongoDBStore for league operations
    mongo_store = PBMongoDBStore()
    return PBLeagueService(mongo_store)


@router.post("/league", status_code=status.HTTP_201_CREATED)
def create_league(league: League, pb_league_service: PBLeagueService = Depends(get_pb_league_service)):
    """Create a new league."""
    pb_league_service.save_league_details(league)
    return {"message": "League created successfully", "league_id": league.league_id}
