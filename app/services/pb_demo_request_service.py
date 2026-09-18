import logging
from datetime import datetime, timezone

from app.store.mongo.pb_demo_request_store import PBDemoRequestStore
from app.vo.pb.demo_request import DemoRequest


class PBDemoRequestService:
    """Handles "Book a demo" submissions from the landing site.

    The form is public and unauthenticated, so the service only stores a
    normalised copy of the request (plus the client IP for basic abuse
    triage). Follow-up is manual: the platform console lists the requests.
    """

    def __init__(self, store: PBDemoRequestStore):
        self.store = store
        self.logger = logging.getLogger(__name__)

    def submit(self, req: DemoRequest, client_ip: str | None = None) -> str:
        doc = {
            "name": req.name,
            "email": req.email.strip().lower(),
            "club_name": req.club_name,
            "phone": req.phone,
            "club_size": req.club_size,
            "preferred_time": req.preferred_time,
            "message": req.message,
            "client_ip": client_ip,
            "status": "new",
            "created_at": datetime.now(timezone.utc),
        }
        request_id = self.store.insert(doc)
        self.logger.info("Demo requested by %s (%s)", doc["email"], doc["club_name"])
        return request_id

    def list_recent(self, limit: int = 200) -> list[dict]:
        return self.store.list_recent(limit)
