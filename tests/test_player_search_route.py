import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_player
from app.api.v1.routers.pickleball import pb_player
from app.vo.pb.player import PlayerResponse, PlayerSearchResponse, PlayerSearchResult

SEARCHER = "me@example.com"


class PlayerSearchRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.search_players.return_value = PlayerSearchResponse(
            results=[PlayerSearchResult(
                id="1", firstName="Bea", lastName="Baker", email="bea@example.com",
                dupr_rating=4.0, distance_miles=4.2)],
            count=1, origin_zip="20147", radius_miles=25,
        )
        # The sibling /players/{league_id} handler shares this mock and has its own
        # response_model, so it needs a serializable return value.
        self.service.get_player_by_league_id.return_value = PlayerResponse(
            id="1", firstName="Bea", lastName="Baker", email="bea@example.com", dupr_rating=4.0)
        app = FastAPI()
        app.include_router(pb_player.router, prefix="/api/v1")
        app.dependency_overrides[pb_player.get_pb_player_service] = lambda: self.service
        app.dependency_overrides[get_current_player] = lambda: {"sub": SEARCHER, "role": "player"}
        self.app = app
        self.client = TestClient(app)


class TestRouteDeclarationOrder(PlayerSearchRouteTestCase):
    """`/players/{league_id}` is declared in the same router. If it came first,
    FastAPI would match every search as league_id="search"."""

    def test_search_reaches_the_search_handler(self):
        resp = self.client.get("/api/v1/players/search?first_name=bea")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.service.search_players.assert_called_once()
        self.service.get_player_by_league_id.assert_not_called()

    def test_a_real_league_id_still_reaches_the_other_handler(self):
        self.client.get("/api/v1/players/some-league-id")
        self.service.get_player_by_league_id.assert_called_once_with("some-league-id")
        self.service.search_players.assert_not_called()


class TestQueryContract(PlayerSearchRouteTestCase):
    def test_every_parameter_is_forwarded(self):
        self.client.get("/api/v1/players/search"
                        "?first_name=bea&last_name=baker&dupr_min=3.5&dupr_max=4.5"
                        "&radius_miles=25&origin_zip=20147&limit=50")
        kwargs = self.service.search_players.call_args.kwargs
        self.assertEqual(kwargs, {
            "searcher_email": SEARCHER, "first_name": "bea", "last_name": "baker",
            "dupr_min": 3.5, "dupr_max": 4.5, "radius_miles": 25.0,
            "origin_zip": "20147", "limit": 50,
        })

    def test_no_filters_defaults_to_none_with_a_capped_limit(self):
        self.client.get("/api/v1/players/search")
        kwargs = self.service.search_players.call_args.kwargs
        self.assertEqual(kwargs["limit"], 200)
        for key in ("first_name", "last_name", "dupr_min", "dupr_max", "radius_miles", "origin_zip"):
            self.assertIsNone(kwargs[key])

    def test_the_response_shape_survives_serialization(self):
        body = self.client.get("/api/v1/players/search?radius_miles=25").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["origin_zip"], "20147")
        self.assertEqual(body["results"][0]["distance_miles"], 4.2)

    def test_out_of_range_values_are_422_not_silently_clamped(self):
        for query in ("dupr_min=9", "dupr_max=-1", "radius_miles=0",
                      "radius_miles=501", "limit=0", "limit=9999"):
            with self.subTest(query=query):
                resp = self.client.get(f"/api/v1/players/search?{query}")
                self.assertEqual(resp.status_code, 422, resp.text)
        self.service.search_players.assert_not_called()

    def test_search_requires_authentication(self):
        self.app.dependency_overrides.pop(get_current_player)
        resp = self.client.get("/api/v1/players/search?first_name=bea")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
