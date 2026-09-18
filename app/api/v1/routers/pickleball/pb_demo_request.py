from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.deps import get_current_superadmin
from app.services.pb_demo_request_service import PBDemoRequestService
from app.store.mongo.pb_demo_request_store import PBDemoRequestStore
from app.vo.pb.demo_request import DemoRequest, DemoRequestResponse

router = APIRouter(tags=["Demo"])


def get_demo_request_service() -> PBDemoRequestService:
    """Dependency injector for PBDemoRequestService."""
    return PBDemoRequestService(PBDemoRequestStore())


@router.post("/book-demo", status_code=status.HTTP_201_CREATED, response_model=DemoRequestResponse)
def book_demo(
    req: DemoRequest,
    request: Request,
    svc: PBDemoRequestService = Depends(get_demo_request_service),
):
    """Public: record a "Book a demo" request from the landing site."""
    try:
        request_id = svc.submit(req, client_ip=request.client.host if request.client else None)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit demo request: {str(e)}",
        )
    return DemoRequestResponse(
        request_id=request_id,
        message="Thanks! We'll be in touch within one business day to schedule your demo.",
    )


@router.get("/platform-console/demo-requests", include_in_schema=False)
def list_demo_requests(
    limit: int = Query(200, ge=1, le=1000),
    _: dict = Depends(get_current_superadmin),
    svc: PBDemoRequestService = Depends(get_demo_request_service),
):
    """Superadmin: most-recent-first list of demo requests."""
    return svc.list_recent(limit)
