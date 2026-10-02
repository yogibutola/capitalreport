"""Who may call what: ownership, self-only reads, token-only identity, and the
public tournament view.

Real signed tokens go through the real auth dependencies; only the services and
stores behind the routers are mocked.
"""
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1.deps import is_club_owner, require_club_owner, require_self
from app.api.v1.routers.pickleball import pb_group, pb_league, pb_player, pb_tournament
from app.services.pb_league_service import PBLeagueService
from app.services.pb_player_service import PBPlayerService
from app.services.pb_tournament_service import PBTournamentService
from app.utils.security import create_access_token
from app.vo.pb.player import ForgotPasswordRequest, PlayerResponse

PLAYER = "pat@example.com"
OTHER = "olive@example.com"
CLUB = "club@example.com"
OTHER_CLUB = "rival@example.com"
LEAGUE_ID = str(ObjectId())
TOURNAMENT_ID = str(ObjectId())


def _auth(email: str, role: str = "player") -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': email, 'role': role})}"}


def _app(router, dep, service) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[dep] = lambda: service
    return TestClient(app)


class TestDepsHelpers(unittest.TestCase):
    def test_require_self_allows_own_email_case_insensitively(self):
        require_self("Pat@Example.com ", {"sub": PLAYER})

    def test_require_self_rejects_someone_else(self):
        with self.assertRaises(HTTPException) as ctx:
            require_self(OTHER, {"sub": PLAYER})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_self_lets_the_platform_admin_read_anyone(self):
        require_self(OTHER, {"sub": "ops@example.com", "role": "superadmin"})

    def test_club_owner_needs_admin_role_and_matching_email(self):
        self.assertTrue(is_club_owner("Club@Example.com", {"sub": CLUB, "role": "admin"}))
        self.assertFalse(is_club_owner(CLUB, {"sub": OTHER_CLUB, "role": "admin"}))
        # A player whose email happens to equal the club_id is still not the club.
        self.assertFalse(is_club_owner(CLUB, {"sub": CLUB, "role": "player"}))

    def test_resource_without_an_owner_belongs_to_nobody(self):
        self.assertFalse(is_club_owner(None, {"sub": CLUB, "role": "admin"}))
        with self.assertRaises(HTTPException) as ctx:
            require_club_owner(None, {"sub": CLUB, "role": "admin"})
        self.assertEqual(ctx.exception.status_code, 403)


class LeagueRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.get_league_owner.return_value = {"club_id": CLUB}
        self.service.get_match_participant_emails.return_value = {PLAYER, "b@x.com", "c@x.com", "d@x.com"}
        self.service.delete_league.return_value = True
        self.service.get_league_details_by_league_name.return_value = {"league_name": "Tue"}
        self.service.get_matches_by_player_email.return_value = []
        self.client = _app(pb_league.router, pb_league.get_pb_league_service, self.service)

    def _score(self, email, role="player", match_league=LEAGUE_ID):
        return self.client.post("/api/v1/league/match/score", headers=_auth(email, role), json={
            "league_id": match_league, "match_id": "m1",
            "score_team_1": 11, "score_team_2": 7, "match_status": "completed"})


class TestLeagueReads(LeagueRouteTestCase):
    def test_roster_endpoints_need_a_signed_in_caller(self):
        for path in (f"/api/v1/league/name/Tue", f"/api/v1/league/id/{LEAGUE_ID}", "/api/v1/league/active"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_signed_in_player_can_open_a_league(self):
        resp = self.client.get("/api/v1/league/name/Tue", headers=_auth(PLAYER))
        self.assertEqual(resp.status_code, 200)

    def test_all_leagues_stays_public(self):
        self.service.get_all_leagues.return_value = []
        self.assertEqual(self.client.get("/api/v1/all_leagues").status_code, 200)

    def test_match_history_is_own_only(self):
        self.assertEqual(self.client.get(f"/api/v1/player/{OTHER}/matches", headers=_auth(PLAYER)).status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/player/{PLAYER}/matches", headers=_auth(PLAYER)).status_code, 200)
        self.service.get_matches_by_player_email.assert_called_once_with(PLAYER)


class TestLeagueRegistration(LeagueRouteTestCase):
    def test_registers_the_token_subject_not_the_body_email(self):
        resp = self.client.post("/api/v1/league/register", headers=_auth(PLAYER),
                                json={"league_id": LEAGUE_ID, "email": OTHER})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.service.register_player.assert_called_once_with(LEAGUE_ID, PLAYER)

    def test_body_email_is_optional(self):
        resp = self.client.post("/api/v1/league/register", headers=_auth(PLAYER), json={"league_id": LEAGUE_ID})
        self.assertEqual(resp.status_code, 200, resp.text)


class TestLeagueScoring(LeagueRouteTestCase):
    def test_a_participant_can_score(self):
        self.assertEqual(self._score(PLAYER).status_code, 200)
        self.service.save_match_score.assert_called_once()

    def test_the_owning_club_can_score(self):
        self.assertEqual(self._score(CLUB, role="admin").status_code, 200)

    def test_a_bystander_cannot_score(self):
        self.assertEqual(self._score(OTHER).status_code, 403)
        self.service.save_match_score.assert_not_called()

    def test_another_club_cannot_score(self):
        self.assertEqual(self._score(OTHER_CLUB, role="admin").status_code, 403)
        self.service.save_match_score.assert_not_called()

    def test_unknown_match_is_404(self):
        self.service.get_match_participant_emails.return_value = None
        self.assertEqual(self._score(PLAYER).status_code, 404)


class TestLeagueOwnership(LeagueRouteTestCase):
    def test_only_the_owning_club_can_delete(self):
        resp = self.client.delete(f"/api/v1/league/{LEAGUE_ID}", headers=_auth(OTHER_CLUB, "admin"))
        self.assertEqual(resp.status_code, 403)
        self.service.delete_league.assert_not_called()

        resp = self.client.delete(f"/api/v1/league/{LEAGUE_ID}", headers=_auth(CLUB, "admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.service.delete_league.assert_called_once_with(LEAGUE_ID)

    def test_unknown_league_is_404_not_500(self):
        self.service.get_league_owner.return_value = None
        resp = self.client.delete(f"/api/v1/league/{LEAGUE_ID}", headers=_auth(CLUB, "admin"))
        self.assertEqual(resp.status_code, 404)

    def test_only_the_owning_club_can_slot_a_play_day(self):
        resp = self.client.post(f"/api/v1/league/{LEAGUE_ID}/day/1/slot", headers=_auth(OTHER_CLUB, "admin"))
        self.assertEqual(resp.status_code, 403)
        self.service.slot_first_round_of_day.assert_not_called()

        resp = self.client.post(f"/api/v1/league/{LEAGUE_ID}/day/1/slot", headers=_auth(CLUB, "admin"))
        self.assertEqual(resp.status_code, 200, resp.text)

    def _round_payload(self, match_league_id):
        player = {"firstName": "A", "lastName": "B", "email": PLAYER}
        team = {"team_id": "t", "team_name": "Team 1", "player_one": player, "player_two": player, "score": 0}
        match = {"league_id": match_league_id, "league_name": "Tue", "round_id": 1, "group_id": 1,
                 "match_id": "m1", "team_one": team, "team_two": team,
                 "time": "2026-10-01T18:00:00", "court_number": 1}
        return {"league_id": LEAGUE_ID, "league_name": "Tue",
                "rounds": [{"round_id": 1, "group": [{"group_id": 1, "group_name": "Group 1", "match": [match]}]}]}

    def test_only_the_owning_club_can_post_rounds(self):
        resp = self.client.post("/api/v1/league/round", headers=_auth(OTHER_CLUB, "admin"),
                                json=self._round_payload(LEAGUE_ID))
        self.assertEqual(resp.status_code, 403)
        self.service.update_league_with_round_details.assert_not_called()

        resp = self.client.post("/api/v1/league/round", headers=_auth(CLUB, "admin"),
                                json=self._round_payload(LEAGUE_ID))
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_rounds_cannot_carry_matches_for_another_league(self):
        resp = self.client.post("/api/v1/league/round", headers=_auth(CLUB, "admin"),
                                json=self._round_payload(str(ObjectId())))
        self.assertEqual(resp.status_code, 400)
        self.service.update_league_with_round_details.assert_not_called()


class TestPlayerRoutes(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.get_all_players.return_value = [PlayerResponse(
            id="1", firstName="Olive", lastName="O", email=OTHER, dupr_rating=3.5,
            leagues=[{"league_id": LEAGUE_ID, "league_name": "Tue"}])]
        self.service.get_league_by_player_email.return_value = {"leagues": []}
        self.client = _app(pb_player.router, pb_player.get_pb_player_service, self.service)

    def test_player_list_needs_a_signed_in_caller(self):
        self.assertEqual(self.client.get("/api/v1/players").status_code, 401)

    def test_player_list_leaves_out_other_players_leagues(self):
        body = self.client.get("/api/v1/players", headers=_auth(PLAYER)).json()
        self.assertEqual(body[0]["firstName"], "Olive")
        self.assertEqual(body[0]["leagues"], [])

    def test_league_list_by_email_is_own_only(self):
        self.assertEqual(self.client.get(f"/api/v1/player/league/{OTHER}", headers=_auth(PLAYER)).status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/player/league/{PLAYER}", headers=_auth(PLAYER)).status_code, 200)


class TestTournamentRoutes(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.get_tournament_owner.return_value = {"club_id": CLUB}
        self.service.get_public_tournament.return_value = {"tournament_id": TOURNAMENT_ID, "tournament_name": "Fall Open"}
        self.service.get_tournament_by_id.return_value = {
            "tournament_id": TOURNAMENT_ID, "tournament_name": "Fall Open", "players": [{"email": OTHER}]}
        self.service.generate_draw.return_value = {"pools": 2}
        self.service.record_match_score.return_value = {"tournament_id": TOURNAMENT_ID}
        self.service.delete_tournament.return_value = True
        self.service.get_tournaments_by_player_email.return_value = []
        self.client = _app(pb_tournament.router, pb_tournament.get_pb_tournament_service, self.service)

    def test_anonymous_visitor_gets_the_public_view_only(self):
        body = self.client.get(f"/api/v1/tournament/id/{TOURNAMENT_ID}").json()
        self.assertEqual(body["tournament_name"], "Fall Open")
        self.assertNotIn("players", body)
        self.service.get_tournament_by_id.assert_not_called()

    def test_a_bad_token_is_treated_as_anonymous(self):
        resp = self.client.get(f"/api/v1/tournament/id/{TOURNAMENT_ID}",
                               headers={"Authorization": "Bearer not-a-jwt"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("players", resp.json())

    def test_signed_in_player_gets_the_full_tournament(self):
        body = self.client.get(f"/api/v1/tournament/id/{TOURNAMENT_ID}", headers=_auth(PLAYER)).json()
        self.assertIn("players", body)

    def test_unknown_tournament_is_404_for_anonymous_visitors(self):
        self.service.get_public_tournament.return_value = None
        self.assertEqual(self.client.get(f"/api/v1/tournament/id/{TOURNAMENT_ID}").status_code, 404)

    def test_player_tournament_list_is_own_only(self):
        self.assertEqual(self.client.get(f"/api/v1/player/tournaments/{OTHER}").status_code, 401)
        self.assertEqual(
            self.client.get(f"/api/v1/player/tournaments/{OTHER}", headers=_auth(PLAYER)).status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/v1/player/tournaments/{PLAYER}", headers=_auth(PLAYER)).status_code, 200)

    def test_registers_the_token_subject_not_the_body_email(self):
        resp = self.client.post("/api/v1/tournament/register", headers=_auth(PLAYER),
                                json={"tournament_id": TOURNAMENT_ID, "email": OTHER})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self.service.register.call_args.args[2], PLAYER)

    def test_admin_actions_require_the_owning_club(self):
        calls = [
            ("post", f"/api/v1/tournament/{TOURNAMENT_ID}/draw", None, self.service.generate_draw),
            ("post", f"/api/v1/tournament/{TOURNAMENT_ID}/match/score",
             {"match_id": "p1", "stage": "pool", "score_one": 16, "score_two": 9}, self.service.record_match_score),
            ("post", f"/api/v1/tournament/{TOURNAMENT_ID}/reopen", None, self.service.reopen_registration),
            ("delete", f"/api/v1/tournament/{TOURNAMENT_ID}", None, self.service.delete_tournament),
        ]
        for method, path, body, service_call in calls:
            with self.subTest(path=path, method=method):
                kwargs = {"json": body} if body else {}
                resp = getattr(self.client, method)(path, headers=_auth(OTHER_CLUB, "admin"), **kwargs)
                self.assertEqual(resp.status_code, 403, resp.text)
                service_call.assert_not_called()

                resp = getattr(self.client, method)(path, headers=_auth(CLUB, "admin"), **kwargs)
                self.assertEqual(resp.status_code, 200, resp.text)
                service_call.assert_called_once()


class TestGroupRoutes(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.group = {"group_id": "g1", "name": "Tuesday crew", "creator_email": PLAYER,
                      "members": [PLAYER], "events": [], "messages": [], "created_at": "2026-10-01"}
        self.store.get_group_by_id.return_value = self.group
        self.store.create_group.return_value = self.group
        self.store.get_groups_for_player.return_value = [self.group]
        self.store.set_event_vote.return_value = {
            "voter_email": PLAYER, "voter_name": "Pat", "vote": "In", "timestamp": "t"}
        self.store.add_group_message.return_value = {
            "message_id": "m", "author_email": PLAYER, "author_name": "Pat", "content": "hi", "timestamp": "t"}
        self.client = _app(pb_group.router, pb_group.get_group_store, self.store)

    def test_every_group_route_needs_a_signed_in_caller(self):
        for method, path in (("post", "/api/v1/groups"), ("get", f"/api/v1/groups/player/{PLAYER}"),
                             ("get", "/api/v1/groups/g1"), ("post", "/api/v1/groups/g1/members"),
                             ("post", "/api/v1/groups/g1/events"), ("post", "/api/v1/groups/g1/events/e1/vote"),
                             ("post", "/api/v1/groups/g1/messages"),
                             ("post", "/api/v1/groups/g1/events/e1/messages")):
            with self.subTest(path=path):
                kwargs = {"json": {}} if method == "post" else {}
                self.assertEqual(getattr(self.client, method)(path, **kwargs).status_code, 401)

    def test_creator_is_the_token_subject(self):
        resp = self.client.post("/api/v1/groups", headers=_auth(PLAYER),
                                json={"name": "Tuesday crew", "creator_email": OTHER})
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(self.store.create_group.call_args.kwargs["creator_email"], PLAYER)

    def test_non_members_cannot_read_or_write(self):
        self.assertEqual(self.client.get("/api/v1/groups/g1", headers=_auth(OTHER)).status_code, 403)
        resp = self.client.post("/api/v1/groups/g1/members", headers=_auth(OTHER), json={"email": OTHER})
        self.assertEqual(resp.status_code, 403)
        self.store.add_member.assert_not_called()

    def test_unknown_group_is_404(self):
        self.store.get_group_by_id.return_value = None
        self.assertEqual(self.client.get("/api/v1/groups/nope", headers=_auth(PLAYER)).status_code, 404)

    def test_group_list_by_email_is_own_only(self):
        self.assertEqual(self.client.get(f"/api/v1/groups/player/{OTHER}", headers=_auth(PLAYER)).status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/groups/player/{PLAYER}", headers=_auth(PLAYER)).status_code, 200)

    def test_vote_and_message_are_attributed_to_the_token_subject(self):
        resp = self.client.post("/api/v1/groups/g1/events/e1/vote", headers=_auth(PLAYER),
                                json={"voter_email": OTHER, "voter_name": "Pat", "vote": "In"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self.store.set_event_vote.call_args.kwargs["voter_email"], PLAYER)

        resp = self.client.post("/api/v1/groups/g1/messages", headers=_auth(PLAYER),
                                json={"author_email": OTHER, "author_name": "Pat", "content": "hi"})
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(self.store.add_group_message.call_args.kwargs["author_email"], PLAYER)


class TestOwnershipLookups(unittest.TestCase):
    """The service lookups the routers' ownership checks rely on."""

    def _league_service(self, store, match_store=None):
        service = PBLeagueService.__new__(PBLeagueService)
        service.pb_league_store = store
        service.pb_match_store = match_store or MagicMock()
        return service

    def test_malformed_league_id_reads_as_not_found(self):
        store = MagicMock()
        store.get_league_details.side_effect = lambda league_id: ObjectId(league_id)  # raises InvalidId
        self.assertIsNone(self._league_service(store).get_league_owner("not-an-id"))

    def test_league_owner_is_its_club_id(self):
        store = MagicMock()
        store.get_league_details.return_value = {"club_id": CLUB, "players": [{"email": OTHER}]}
        self.assertEqual(self._league_service(store).get_league_owner(LEAGUE_ID), {"club_id": CLUB})

    def test_participants_are_the_four_players_not_the_sitter(self):
        match_store = MagicMock()
        match_store.get_match.return_value = {
            "team_one": {"player_one": {"email": "A@x.com"}, "player_two": {"email": "b@x.com"}},
            "team_two": {"player_one": {"email": "c@x.com"}, "player_two": {"email": "d@x.com"}},
            "siting_player": {"email": "e@x.com"},
        }
        service = self._league_service(MagicMock(), match_store)
        self.assertEqual(service.get_match_participant_emails(LEAGUE_ID, "m1"),
                         {"a@x.com", "b@x.com", "c@x.com", "d@x.com"})

    def test_public_tournament_view_has_no_roster(self):
        store = MagicMock()
        store.get_tournament_details.return_value = {
            "tournament_id": TOURNAMENT_ID, "tournament_name": "Fall Open", "club_id": CLUB,
            "players": [{"email": OTHER}], "registrations": [{"email": OTHER}],
            "teams": [{"player_one_email": OTHER}], "pools": [], "knockout": []}
        public = PBTournamentService(store).get_public_tournament(TOURNAMENT_ID)
        self.assertEqual(public["tournament_name"], "Fall Open")
        for key in ("players", "registrations", "teams", "pools", "knockout", "club_id"):
            self.assertNotIn(key, public)


class TestResetLinkLogging(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.store.find_player_by_email.return_value = {"email": PLAYER}
        self.service = PBPlayerService(self.store)

    def _logged(self) -> str:
        with self.assertLogs("app.services.pb_player_service", level=logging.INFO) as logs:
            self.service.forgot_password(ForgotPasswordRequest(email=PLAYER))
        return "\n".join(logs.output)

    def test_reset_link_is_not_logged_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOG_PASSWORD_RESET_LINKS", None)
            output = self._logged()
        self.assertNotIn("token=", output)
        self.assertIn("link not logged", output)

    def test_reset_link_is_logged_when_a_developer_opts_in(self):
        with patch.dict(os.environ, {"LOG_PASSWORD_RESET_LINKS": "true"}):
            self.assertIn("reset-password?token=", self._logged())


if __name__ == "__main__":
    unittest.main()
