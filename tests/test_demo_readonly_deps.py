import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.v1.deps import get_current_admin, get_current_player


def _request(method: str):
    req = MagicMock()
    req.method = method
    return req


class TestDemoReadOnlyDeps(unittest.TestCase):
    def test_demo_token_blocks_writes_for_player_dep(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.assertRaises(HTTPException) as ctx:
                get_current_player(_request(method), {"sub": "demo.player@x", "demo": True})
            self.assertEqual(ctx.exception.status_code, 403)

    def test_demo_token_allows_reads_for_player_dep(self):
        payload = {"sub": "demo.player@x", "demo": True}
        self.assertIs(get_current_player(_request("GET"), payload), payload)

    def test_demo_token_blocks_writes_for_admin_dep(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_admin(_request("POST"), {"sub": "demo.club@x", "role": "admin", "demo": True})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_demo_token_allows_reads_for_admin_dep(self):
        payload = {"sub": "demo.club@x", "role": "admin", "demo": True}
        self.assertIs(get_current_admin(_request("GET"), payload), payload)

    def test_non_demo_token_can_still_write(self):
        payload = {"sub": "real@x", "role": "admin"}
        self.assertIs(get_current_admin(_request("POST"), payload), payload)
        player = {"sub": "real@x"}
        self.assertIs(get_current_player(_request("POST"), player), player)

    def test_non_admin_still_rejected_before_demo_check(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_admin(_request("GET"), {"sub": "p@x", "role": "player"})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
