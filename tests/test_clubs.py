"""Clubs as their own records: creation, ownership, venues, and what a session
says about the account (role + club_id), plus the v2 shape new accounts get."""
import os
import unittest
from unittest.mock import MagicMock, patch

import jwt
import pydantic
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from app.api.v1.routers.pickleball import pb_club, pb_league
from app.services.pb_club_service import PBClubService, slugify
from app.services.pb_player_service import PBPlayerService
from app.services.pb_session import session_claims
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.schema.players import player_v2_problems
from app.utils.security import ALGORITHM, SECRET_KEY, create_access_token
from app.vo.pb.club import ClubCreate, ClubResponse, ClubUpdate, VenueCreate
from app.vo.pb.player import ChangePasswordRequest, ClubSignup, PlayerLogin, PlayerSignup

PASSWORD = "Passw0rd@1"


def _decode(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


class FakeClubStore:
    """Just enough of PBClubStore, with the two unique indexes enforced."""

    def __init__(self):
        self.clubs, self.venues = {}, {}

    def insert_club(self, doc):
        for c in self.clubs.values():
            if c["owner_player_id"] == doc["owner_player_id"] or c["slug"] == doc["slug"]:
                raise DuplicateKeyError("dup")
        doc = {**doc, "_id": ObjectId()}
        self.clubs[doc["_id"]] = doc
        return doc

    def get_club(self, club_id):
        return self.clubs.get(ObjectId(club_id)) if ObjectId.is_valid(str(club_id)) else None

    def get_club_by_owner(self, player_id):
        return next((c for c in self.clubs.values() if c["owner_player_id"] == player_id), None)

    def slug_exists(self, slug):
        return any(c["slug"] == slug for c in self.clubs.values())

    def update_club(self, club_id, fields):
        club = self.get_club(club_id)
        if club:
            club.update(fields)
        return club

    def insert_venue(self, club_id, doc):
        doc = {**doc, "_id": ObjectId(), "club_id": ObjectId(club_id)}
        self.venues[doc["_id"]] = doc
        return doc

    def list_venues(self, club_id):
        return [v for v in self.venues.values() if v["club_id"] == ObjectId(club_id)]

    def update_venue(self, club_id, venue_id, fields):
        v = self.venues.get(ObjectId(venue_id))
        if not v or v["club_id"] != ObjectId(club_id):
            return None
        v.update(fields)
        return v

    def delete_venue(self, club_id, venue_id):
        v = self.venues.get(ObjectId(venue_id))
        if not v or v["club_id"] != ObjectId(club_id):
            return False
        del self.venues[v["_id"]]
        return True


def _owner(email="dana@example.com"):
    return {"_id": ObjectId(), "email": email, "firstName": "Dana", "lastName": "Dink", "dupr_rating": 4.0}


class TestSlugify(unittest.TestCase):
    def test_slugs(self):
        self.assertEqual(slugify("St. Paul's Paddle Club"), "st-pauls-paddle-club")
        self.assertEqual(slugify("  Café  Dink!! "), "cafe-dink")
        self.assertEqual(slugify("!!!"), "club")
        self.assertLessEqual(len(slugify("x" * 200)), 60)


class TestCreateClub(unittest.TestCase):
    def setUp(self):
        self.players = MagicMock()
        self.owner = _owner()
        self.players.find_player_by_email.return_value = self.owner
        self.clubs = FakeClubStore()
        self.service = PBClubService(self.clubs, self.players)

    def test_creates_a_club_owned_by_the_caller_and_returns_an_admin_session(self):
        resp = self.service.create_club("dana@example.com", ClubCreate(name="Downtown Dinkers", phone=" 555 "))
        club = self.clubs.get_club_by_owner(self.owner["_id"])
        self.assertEqual(club["name"], "Downtown Dinkers")
        self.assertEqual(club["slug"], "downtown-dinkers")
        self.assertEqual(club["phone"], "555")
        self.assertEqual(club["contact_email"], "dana@example.com")  # defaults to the owner's
        claims = _decode(resp.token)
        self.assertEqual(claims["role"], "admin")
        self.assertEqual(claims["club_id"], str(club["_id"]))
        self.assertEqual(claims["sub"], "dana@example.com")
        self.assertEqual(resp.club.id, str(club["_id"]))

    def test_one_club_per_person(self):
        self.service.create_club("dana@example.com", ClubCreate(name="Downtown Dinkers"))
        with self.assertRaises(HTTPException) as ctx:
            self.service.create_club("dana@example.com", ClubCreate(name="Second Club"))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_same_name_gets_a_distinct_slug(self):
        self.service.create_club("dana@example.com", ClubCreate(name="Dinkers"))
        other = _owner("eve@example.com")
        self.players.find_player_by_email.return_value = other
        self.service.create_club("eve@example.com", ClubCreate(name="Dinkers"))
        self.assertEqual(self.clubs.get_club_by_owner(other["_id"])["slug"], "dinkers-2")

    def test_a_parallel_create_for_the_same_owner_is_a_409(self):
        # The unique owner index is the real guard when two requests race the check.
        with patch.object(self.clubs, "get_club_by_owner", side_effect=[None, {"_id": ObjectId()}]), \
                patch.object(self.clubs, "insert_club", side_effect=DuplicateKeyError("dup")):
            with self.assertRaises(HTTPException) as ctx:
                self.service.create_club("dana@example.com", ClubCreate(name="Dinkers"))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_unknown_account_is_404(self):
        self.players.find_player_by_email.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            self.service.create_club("ghost@example.com", ClubCreate(name="Dinkers"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_name_is_required(self):
        with self.assertRaises(pydantic.ValidationError):
            ClubCreate(name="  ")


class TestUpdateClubAndVenues(unittest.TestCase):
    def setUp(self):
        self.clubs = FakeClubStore()
        self.service = PBClubService(self.clubs, MagicMock())
        self.club = self.clubs.insert_club({"owner_player_id": ObjectId(), "name": "Dinkers", "slug": "dinkers"})
        self.club_id = str(self.club["_id"])

    def test_renaming_keeps_the_slug(self):
        resp = self.service.update_club(self.club_id, ClubUpdate(name="Uptown Dinkers"))
        self.assertEqual(resp.name, "Uptown Dinkers")
        self.assertEqual(resp.slug, "dinkers")

    def test_unknown_club_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.update_club(str(ObjectId()), ClubUpdate(phone="1"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_venue_lifecycle(self):
        venue = self.service.add_venue(self.club_id, VenueCreate(
            name="Baseline Courts", zip_code="97205", courts=[{"number": 1}, {"number": 2, "label": "Stadium"}]))
        self.assertEqual([c.number for c in venue.courts], [1, 2])
        self.assertEqual([v.name for v in self.service.list_venues(self.club_id)], ["Baseline Courts"])

        updated = self.service.update_venue(self.club_id, venue.id, VenueCreate(name="Baseline Park"))
        self.assertEqual(updated.name, "Baseline Park")
        self.service.delete_venue(self.club_id, venue.id)
        self.assertEqual(self.service.list_venues(self.club_id), [])

    def test_a_club_cannot_touch_another_clubs_venue(self):
        venue = self.service.add_venue(self.club_id, VenueCreate(name="Ours"))
        rival_id = str(ObjectId())
        for call in (lambda: self.service.update_venue(rival_id, venue.id, VenueCreate(name="Theirs")),
                     lambda: self.service.delete_venue(rival_id, venue.id)):
            with self.assertRaises(HTTPException) as ctx:
                call()
            self.assertEqual(ctx.exception.status_code, 404)

    def test_court_numbers_must_be_unique(self):
        with self.assertRaises(pydantic.ValidationError):
            VenueCreate(name="X", courts=[{"number": 1}, {"number": 1}])


class TestSessionClaims(unittest.TestCase):
    def setUp(self):
        self.player = _owner()
        self.club = {"_id": ObjectId()}

    def test_player_owner_and_superadmin(self):
        with patch.dict(os.environ, {"SUPERADMIN_EMAILS": "boss@example.com"}):
            plain = session_claims(self.player, None)
            owner = session_claims(self.player, self.club)
            boss = session_claims({**self.player, "email": "boss@example.com"}, self.club)
        self.assertEqual(plain["role"], "player")
        self.assertNotIn("club_id", plain)
        self.assertEqual((owner["role"], owner["club_id"]), ("admin", str(self.club["_id"])))
        self.assertEqual(boss["role"], "superadmin")  # platform role wins
        self.assertEqual(plain["pid"], str(self.player["_id"]))

    def test_demo_flag(self):
        self.assertTrue(session_claims(self.player, None, demo=True)["demo"])
        self.assertNotIn("demo", session_claims(self.player, None))


class TestSigninAndAccounts(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.clubs = FakeClubStore()
        self.service = PBPlayerService(self.store, self.clubs)
        self.hash = self.service.hash_password(PASSWORD)

    def _signin(self, doc):
        self.store.find_player_by_email.return_value = doc
        with patch.object(PBPlayerService, "_audit_signin"):
            return self.service.signin_player(PlayerLogin(email=doc["email"], password=PASSWORD))

    def test_owner_signs_in_as_admin_with_their_club(self):
        owner = {**_owner(), "password_hash": self.hash}
        club = self.clubs.insert_club({"owner_player_id": owner["_id"], "name": "Dinkers", "slug": "dinkers"})
        resp = self._signin(owner)
        self.assertEqual(resp.role, "admin")
        self.assertEqual(resp.clubName, "Dinkers")
        self.assertEqual(_decode(resp.token)["club_id"], str(club["_id"]))

    def test_a_pre_migration_document_still_signs_in(self):
        # Until the v2 migration runs, documents carry `password` and a stored role.
        legacy = {**_owner(), "password": self.hash, "role": "admin"}
        resp = self._signin(legacy)
        # A stored role no longer grants anything: no club, no admin.
        self.assertEqual(resp.role, "player")

    def test_wrong_password_is_401(self):
        self.store.find_player_by_email.return_value = {**_owner(), "password_hash": self.hash}
        with patch.object(PBPlayerService, "_audit_signin"), self.assertRaises(HTTPException) as ctx:
            self.service.signin_player(PlayerLogin(email="dana@example.com", password="Wrong@123"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_new_accounts_are_written_in_the_v2_shape(self):
        self.store.find_player_by_email.return_value = None
        self.store.create_player.side_effect = lambda doc: {**doc, "_id": ObjectId()}
        resp = self.service.register_player(PlayerSignup(
            firstName=" Ada ", lastName="Lovelace", email="Ada@Example.com", password=PASSWORD, dupr_rating=3.5))
        doc = self.store.create_player.call_args[0][0]
        self.assertEqual(player_v2_problems(doc), [])
        self.assertEqual(doc["email"], "ada@example.com")
        self.assertEqual(doc["firstName"], "Ada")
        self.assertTrue(self.service.verify_password(PASSWORD, doc["password_hash"]))
        for gone in ("password", "role", "leagues", "clubName"):
            self.assertNotIn(gone, doc)
        self.store.record_rating.assert_called_once()
        self.assertEqual(resp.role, "player")

    def test_signup_race_on_the_unique_email_index_is_a_409(self):
        self.store.find_player_by_email.return_value = None
        self.store.create_player.side_effect = DuplicateKeyError("dup")
        with self.assertRaises(HTTPException) as ctx:
            self.service.register_player(PlayerSignup(
                firstName="Ada", lastName="L", email="ada@example.com", password=PASSWORD, dupr_rating=3.5))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_club_signup_creates_a_person_and_a_club_they_own(self):
        self.store.find_player_by_email.return_value = None
        self.store.create_player.side_effect = lambda doc: {**doc, "_id": ObjectId()}
        resp = self.service.register_club(ClubSignup(
            firstName="Mo", lastName="Reyes", clubName="Metro Paddle", email="mo@example.com",
            password=PASSWORD, address="1 Main St", phone="555"))
        person = self.store.create_player.call_args[0][0]
        self.assertEqual((person["firstName"], person["lastName"]), ("Mo", "Reyes"))
        self.assertIsNone(person["dupr_rating"])
        (club,) = self.clubs.clubs.values()
        self.assertEqual((club["name"], club["address"]), ("Metro Paddle", "1 Main St"))
        self.assertEqual(resp.role, "admin")
        self.assertEqual(_decode(resp.token)["club_id"], str(club["_id"]))

    def test_club_signup_requires_the_organisers_name(self):
        with self.assertRaises(pydantic.ValidationError):
            ClubSignup(clubName="Metro Paddle", email="mo@example.com", password=PASSWORD)

    def test_changing_a_dupr_rating_records_history(self):
        player = {**_owner(), "password_hash": self.hash}
        self.store.find_player_by_email.return_value = player
        self.store.update_player_profile.side_effect = lambda email, updates: {**player, **updates}
        from app.vo.pb.player import ProfileUpdateRequest
        self.service.update_profile(player["email"], ProfileUpdateRequest(dupr_rating=4.5))
        self.store.record_rating.assert_called_once_with(player["_id"], 4.5, "self")
        self.store.record_rating.reset_mock()
        self.service.update_profile(player["email"], ProfileUpdateRequest(dupr_rating=4.0))  # unchanged
        self.store.record_rating.assert_not_called()


class TestPasswordWrites(unittest.TestCase):
    """Writes go to password_hash and drop any pre-v2 password field."""

    def setUp(self):
        self.collection = MagicMock()
        self.store = PBPlayerStore.__new__(PBPlayerStore)
        self.store.logger = MagicMock()
        self.store.get_players_collection = lambda: self.collection

    def test_update_password(self):
        self.store.update_player_password("Dana@Example.com", "newhash")
        flt, update = self.collection.update_one.call_args[0]
        self.assertEqual(flt, {"email": "dana@example.com"})
        self.assertEqual(update["$set"]["password_hash"], "newhash")
        self.assertIn("password", update["$unset"])

    def test_reset_password_consumes_the_token(self):
        self.store.reset_password("dana@example.com", "newhash")
        _, update = self.collection.update_one.call_args[0]
        self.assertEqual(update["$set"]["password_hash"], "newhash")
        self.assertEqual(set(update["$unset"]), {"password", "reset_token_hash", "reset_token_expires"})

    def test_change_password_checks_whichever_hash_the_doc_has(self):
        store = MagicMock()
        service = PBPlayerService(store, FakeClubStore())
        store.find_player_by_email.return_value = {**_owner(), "password": service.hash_password(PASSWORD)}
        service.change_password("dana@example.com", ChangePasswordRequest(
            current_password=PASSWORD, new_password="Newer@123"))
        store.update_player_password.assert_called_once()


class TestClubRoutes(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.club_id = str(ObjectId())
        self.service.get_club.return_value = ClubResponse(id=self.club_id, name="Dinkers", slug="dinkers")
        self.service.list_venues.return_value = []
        app = FastAPI()
        app.include_router(pb_club.router, prefix="/api/v1")
        app.dependency_overrides[pb_club.get_pb_club_service] = lambda: self.service
        self.client = TestClient(app)

    def _auth(self, **claims):
        return {"Authorization": f"Bearer {create_access_token({'sub': 'dana@example.com', **claims})}"}

    def test_creating_a_club_needs_a_signed_in_account(self):
        self.assertEqual(self.client.post("/api/v1/clubs", json={"name": "Dinkers"}).status_code, 401)

    def test_create_uses_the_token_subject(self):
        self.service.create_club.return_value = {
            "club": {"id": self.club_id, "name": "Dinkers", "slug": "dinkers"}, "token": "t"}
        resp = self.client.post("/api/v1/clubs", json={"name": "Dinkers"}, headers=self._auth(role="player"))
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(self.service.create_club.call_args[0][0], "dana@example.com")

    def test_my_club_is_the_one_in_the_token(self):
        resp = self.client.get("/api/v1/clubs/me", headers=self._auth(role="admin", club_id=self.club_id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.service.get_club.assert_called_once_with(self.club_id)

    def test_players_have_no_club_to_manage(self):
        self.assertEqual(self.client.get("/api/v1/clubs/me", headers=self._auth(role="player")).status_code, 403)

    def test_venues_are_scoped_to_the_tokens_club(self):
        self.client.get("/api/v1/clubs/me/venues", headers=self._auth(role="admin", club_id=self.club_id))
        self.service.list_venues.assert_called_once_with(self.club_id)


class TestLeaguesBelongToTheClub(unittest.TestCase):
    def test_new_league_and_my_leagues_use_the_tokens_club_id(self):
        service = MagicMock()
        service.get_leagues_by_club.return_value = []
        app = FastAPI()
        app.include_router(pb_league.router, prefix="/api/v1")
        app.dependency_overrides[pb_league.get_pb_league_service] = lambda: service
        client = TestClient(app)
        club_id = str(ObjectId())
        headers = {"Authorization": "Bearer " + create_access_token(
            {"sub": "dana@example.com", "role": "admin", "club_id": club_id})}

        def save(league):
            league.league_id = str(ObjectId())
        service.save_league_details.side_effect = save

        resp = client.post("/api/v1/league", headers=headers, json={
            "league_name": "Tuesday Ladder", "league_start_date": "10-06-2026", "group_size": 4,
            "match_format": "Doubles", "club_id": "someone-else"})
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(service.save_league_details.call_args[0][0].club_id, club_id)

        client.get("/api/v1/my_leagues", headers=headers)
        service.get_leagues_by_club.assert_called_once_with(club_id)


if __name__ == "__main__":
    unittest.main()
