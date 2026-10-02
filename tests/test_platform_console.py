import unittest
from unittest.mock import MagicMock

from bson import ObjectId
from fastapi import HTTPException

from app.services.pb_platform_service import PBPlatformService
from app.vo.pb.player import ClubSignup, PlayerSignup


class TestPlatformService(unittest.TestCase):
    def setUp(self):
        self.players = MagicMock()
        self.leagues = MagicMock()
        self.tournaments = MagicMock()
        self.audit = MagicMock()
        self.clubs = MagicMock()
        self.clubs.get_club_by_owner.return_value = None
        self.svc = PBPlatformService(self.players, self.leagues, self.tournaments, self.audit, self.clubs)

    # ---- clubs ----------------------------------------------------------------

    def test_list_clubs_reads_the_clubs_collection_and_annotates_counts(self):
        club_id, owner_id = ObjectId(), ObjectId()
        self.clubs.list_clubs.return_value = [
            {"_id": club_id, "name": "Aces", "owner_player_id": owner_id, "address": "1 Court St"},
        ]
        self.players.find_player_by_id.return_value = {"_id": owner_id, "email": "owner@aces.com"}
        self.leagues.get_leagues_by_club.return_value = [{}, {}]
        self.tournaments.get_tournaments_by_club.return_value = [{}]

        clubs = self.svc.list_clubs()

        self.assertEqual(clubs[0]["id"], str(club_id))
        self.assertEqual(clubs[0]["clubName"], "Aces")
        self.assertEqual(clubs[0]["email"], "owner@aces.com")
        self.assertEqual(clubs[0]["league_count"], 2)
        self.assertEqual(clubs[0]["tournament_count"], 1)
        # Leagues/tournaments belong to the club's id, not anyone's email.
        self.leagues.get_leagues_by_club.assert_called_once_with(str(club_id))

    def test_create_club_delegates_to_registration(self):
        payload = ClubSignup(firstName="Ana", lastName="Ace", clubName="Aces",
                             email="a@club.com", password="Secret@123")
        self.svc.player_service.register_club = MagicMock()
        self.svc.player_service.register_club.return_value.model_dump.return_value = {"email": "a@club.com"}

        result = self.svc.create_club(payload)

        self.svc.player_service.register_club.assert_called_once_with(payload)
        self.assertEqual(result["email"], "a@club.com")

    def test_delete_club_404_when_there_is_no_such_club(self):
        self.clubs.delete_club.return_value = False
        with self.assertRaises(HTTPException) as ctx:
            self.svc.delete_club(str(ObjectId()))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_club_keeps_the_owner_account_and_orphans_leagues(self):
        club_id = str(ObjectId())
        self.clubs.delete_club.return_value = True
        self.svc.delete_club(club_id)
        self.clubs.delete_club.assert_called_once_with(club_id)
        self.players.delete_player_by_email.assert_not_called()
        # Orphan, not cascade: no league/tournament deletes.
        self.leagues.delete_league.assert_not_called()
        self.tournaments.delete_tournament.assert_not_called()

    def test_a_player_who_runs_a_club_cannot_be_deleted(self):
        self.players.find_player_by_email.return_value = {"_id": ObjectId(), "email": "owner@aces.com"}
        self.clubs.get_club_by_owner.return_value = {"_id": ObjectId(), "name": "Aces"}
        with self.assertRaises(HTTPException) as ctx:
            self.svc.delete_player("owner@aces.com")
        self.assertEqual(ctx.exception.status_code, 409)
        self.players.delete_player_by_email.assert_not_called()

    # ---- players ------------------------------------------------------------

    def test_delete_player_purges_from_leagues_and_tournaments(self):
        self.players.find_player_by_email.return_value = {"_id": ObjectId(), "email": "p@x.com"}
        self.leagues.purge_player.return_value = 3
        self.tournaments.purge_player.return_value = 1

        result = self.svc.delete_player("p@x.com")

        self.players.delete_player_by_email.assert_called_once_with("p@x.com")
        self.leagues.purge_player.assert_called_once_with("p@x.com")
        self.tournaments.purge_player.assert_called_once_with("p@x.com")
        self.assertEqual(result["leagues_updated"], 3)
        self.assertEqual(result["tournaments_updated"], 1)

    def test_delete_player_404_when_target_is_a_club(self):
        self.players.find_player_by_email.return_value = {"role": "admin"}
        with self.assertRaises(HTTPException) as ctx:
            self.svc.delete_player("a@club.com")
        self.assertEqual(ctx.exception.status_code, 404)
        self.leagues.purge_player.assert_not_called()

    def test_create_player_delegates_to_registration(self):
        payload = PlayerSignup(
            firstName="Pat", lastName="Lee", email="p@x.com",
            password="Secret@123", dupr_rating=3.5,
        )
        self.svc.player_service.register_player = MagicMock()
        self.svc.player_service.register_player.return_value.model_dump.return_value = {"email": "p@x.com"}

        self.svc.create_player(payload)
        self.svc.player_service.register_player.assert_called_once_with(payload)

    # ---- metrics ----------------------------------------------------------

    def test_metrics_merges_live_totals_and_audit(self):
        self.players.count_by_role.return_value = {"admin": 0, "player": 40}
        self.clubs.count_clubs.return_value = 2
        self.leagues.get_all_leagues.return_value = [{}, {}, {}]
        self.tournaments.get_all_tournaments.return_value = [{}]
        self.audit.metrics.return_value = {"actions_24h": 12, "signins_7d": 5}

        m = self.svc.metrics()

        self.assertEqual(m["total_clubs"], 2)
        self.assertEqual(m["total_players"], 40)
        self.assertEqual(m["total_leagues"], 3)
        self.assertEqual(m["total_tournaments"], 1)
        self.assertEqual(m["actions_24h"], 12)
        self.assertEqual(m["signins_7d"], 5)

    def test_metrics_survives_audit_failure(self):
        self.players.count_by_role.return_value = {"admin": 0, "player": 1}
        self.clubs.count_clubs.return_value = 1
        self.leagues.get_all_leagues.return_value = []
        self.tournaments.get_all_tournaments.return_value = []
        self.audit.metrics.side_effect = RuntimeError("mongo down")

        m = self.svc.metrics()
        self.assertEqual(m["actions_24h"], 0)


if __name__ == "__main__":
    unittest.main()
