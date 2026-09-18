import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.deps import get_current_superadmin
from app.api.v1.routers.pickleball import pb_demo_request
from app.services.pb_demo_request_service import PBDemoRequestService
from app.utils.audit_middleware import action_label
from app.vo.pb.demo_request import DemoRequest


VALID = {
    "name": "Dana Whitfield",
    "email": "Dana@MetroPaddle.com",
    "club_name": "Metro Paddle Club",
    "phone": "+1 555 0100",
    "club_size": "50-150 players",
    "preferred_time": "Weekday mornings",
    "message": "We run three ladders and a summer bracket.",
}


class TestDemoRequestModel(unittest.TestCase):
    def test_valid_payload_is_stripped(self):
        req = DemoRequest(**{**VALID, "name": "  Dana Whitfield  ", "message": "   "})
        self.assertEqual(req.name, "Dana Whitfield")
        self.assertIsNone(req.message)

    def test_blank_required_fields_rejected(self):
        with self.assertRaises(ValidationError):
            DemoRequest(**{**VALID, "name": "   "})
        with self.assertRaises(ValidationError):
            DemoRequest(**{**VALID, "club_name": ""})

    def test_invalid_email_rejected(self):
        with self.assertRaises(ValidationError):
            DemoRequest(**{**VALID, "email": "not-an-email"})

    def test_optional_fields_may_be_omitted(self):
        req = DemoRequest(name="Dana", email="d@x.com", club_name="Club")
        self.assertIsNone(req.phone)
        self.assertIsNone(req.club_size)
        self.assertIsNone(req.preferred_time)


class TestDemoRequestService(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.store.insert.return_value = "abc123"
        self.service = PBDemoRequestService(self.store)

    def test_submit_normalises_and_stores(self):
        request_id = self.service.submit(DemoRequest(**VALID), client_ip="10.0.0.1")

        self.assertEqual(request_id, "abc123")
        self.store.insert.assert_called_once()
        doc = self.store.insert.call_args[0][0]
        self.assertEqual(doc["email"], "dana@metropaddle.com")
        self.assertEqual(doc["club_name"], "Metro Paddle Club")
        self.assertEqual(doc["client_ip"], "10.0.0.1")
        self.assertEqual(doc["status"], "new")
        self.assertIsInstance(doc["created_at"], datetime)
        self.assertEqual(doc["created_at"].tzinfo, timezone.utc)

    def test_list_recent_delegates_to_store(self):
        self.store.list_recent.return_value = [{"id": "1"}]
        self.assertEqual(self.service.list_recent(5), [{"id": "1"}])
        self.store.list_recent.assert_called_once_with(5)


class TestBookDemoRoute(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.store.insert.return_value = "abc123"
        self.store.list_recent.return_value = [{"id": "abc123", "email": "dana@metropaddle.com"}]
        app = FastAPI()
        app.include_router(pb_demo_request.router, prefix="/api/v1")
        app.dependency_overrides[pb_demo_request.get_demo_request_service] = (
            lambda: PBDemoRequestService(self.store)
        )
        self.app = app
        self.client = TestClient(app)

    def test_post_book_demo_is_public_and_returns_201(self):
        resp = self.client.post("/api/v1/book-demo", json=VALID)
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertEqual(body["request_id"], "abc123")
        self.assertIn("in touch", body["message"])
        self.store.insert.assert_called_once()

    def test_post_book_demo_validates_payload(self):
        resp = self.client.post("/api/v1/book-demo", json={**VALID, "email": "nope"})
        self.assertEqual(resp.status_code, 422)
        self.store.insert.assert_not_called()

    def test_list_requires_superadmin(self):
        resp = self.client.get("/api/v1/platform-console/demo-requests")
        self.assertEqual(resp.status_code, 401)

    def test_list_returns_recent_for_superadmin(self):
        self.app.dependency_overrides[get_current_superadmin] = lambda: {"role": "superadmin"}
        resp = self.client.get("/api/v1/platform-console/demo-requests?limit=5")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()[0]["id"], "abc123")
        self.store.list_recent.assert_called_once_with(5)


class TestBookDemoAuditLabel(unittest.TestCase):
    def test_book_demo_has_activity_feed_label(self):
        self.assertEqual(
            action_label("POST", "/api/v1/book-demo", "/api/v1/book-demo"), "Requested a demo"
        )


if __name__ == "__main__":
    unittest.main()
