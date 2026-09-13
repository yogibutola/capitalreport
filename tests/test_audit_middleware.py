import unittest
from unittest.mock import MagicMock

from app.utils.audit_middleware import action_label, _extract_actor, AuditLogMiddleware
from app.utils.security import create_access_token


def _request(headers: dict):
    req = MagicMock()
    req.headers = headers
    return req


class TestActionLabel(unittest.TestCase):
    def test_known_route_template_maps_to_verb(self):
        self.assertEqual(
            action_label("DELETE", "/api/v1/league/{league_id}", "/api/v1/league/abc123"),
            "Deleted a league",
        )

    def test_known_exact_path_maps_to_verb(self):
        self.assertEqual(action_label("POST", None, "/api/v1/signin"), "Signed in")

    def test_unknown_request_falls_back_to_method_and_path(self):
        self.assertEqual(
            action_label("GET", "/api/v1/league/{status}", "/api/v1/league/Active"),
            "GET /api/v1/league/Active",
        )


class TestExtractActor(unittest.TestCase):
    def test_valid_bearer_token_yields_email_and_role(self):
        token = create_access_token({"sub": "boss@x.com", "role": "superadmin"})
        actor, role = _extract_actor(_request({"authorization": f"Bearer {token}"}))
        self.assertEqual(actor, "boss@x.com")
        self.assertEqual(role, "superadmin")

    def test_missing_header_is_anonymous(self):
        self.assertEqual(_extract_actor(_request({})), ("anonymous", None))

    def test_garbage_token_is_anonymous(self):
        actor, role = _extract_actor(_request({"authorization": "Bearer not-a-jwt"}))
        self.assertEqual((actor, role), ("anonymous", None))


class TestShouldAudit(unittest.TestCase):
    def setUp(self):
        self.mw = AuditLogMiddleware(app=MagicMock())
        self.mw._disabled = False

    def _req(self, method, path):
        req = MagicMock()
        req.method = method
        req.url.path = path
        return req

    def test_skips_non_api_paths(self):
        self.assertFalse(self.mw._should_audit(self._req("GET", "/")))

    def test_skips_the_console_its_own_reads(self):
        self.assertFalse(self.mw._should_audit(self._req("GET", "/api/v1/platform-console/clubs")))

    def test_audits_console_writes(self):
        self.assertTrue(self.mw._should_audit(self._req("POST", "/api/v1/platform-console/clubs")))
        self.assertTrue(self.mw._should_audit(self._req("DELETE", "/api/v1/platform-console/players/x@y.com")))

    def test_skips_signin_recorded_explicitly_elsewhere(self):
        self.assertFalse(self.mw._should_audit(self._req("POST", "/api/v1/signin")))

    def test_skips_options_preflight(self):
        self.assertFalse(self.mw._should_audit(self._req("OPTIONS", "/api/v1/league")))

    def test_audits_a_normal_api_write(self):
        self.assertTrue(self.mw._should_audit(self._req("POST", "/api/v1/league")))

    def test_disabled_middleware_audits_nothing(self):
        self.mw._disabled = True
        self.assertFalse(self.mw._should_audit(self._req("POST", "/api/v1/league")))


if __name__ == "__main__":
    unittest.main()
