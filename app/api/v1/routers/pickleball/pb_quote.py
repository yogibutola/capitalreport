from fastapi import status, APIRouter, Depends

from app.services.pb_quote_service import PBQuoteService

router = APIRouter(tags=["Quote"])


def get_pb_quote_service() -> PBQuoteService:
    """Dependency injector for PBQuoteService."""
    return PBQuoteService()


@router.get("/pickleball/quote", status_code=status.HTTP_200_OK)
def get_pickleball_quote(pb_quote_service: PBQuoteService = Depends(get_pb_quote_service)):
    """Return a freshly AI-generated pickleball quote (different on every call)."""
    return {"quote": pb_quote_service.generate_quote()}
