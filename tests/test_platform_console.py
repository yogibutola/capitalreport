import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.services.pb_platform_service import PBPlatformService
from app.vo.pb.player import ClubSignup, PlayerSignup


class TestPlatformService(unittest.TestCase):
    def setUp(self):
        self.players = MagicMock()
        self.leagues = MagicMock()
        self.tournaments = MagicMock()
        self.audit = MagicMock()
        self.svc = PBPlatformService(self.players, self.leagues, self.tournaments, self.audit)

    # ---- clubs ----------------------------------------------------------------

    def test_list_clubs_annotates_counts(self):
        self.players.get_clubs.return_value = [
            {"_id": "1", "email": "a@club.com", "clubName": "Aces", "role": "admin"},
        ]
        self.leagues.get_leagues_by_club.return_value = [{}, {}]
        self.tournaments.get_tournaments_by_club.return_value = [{}]

        clubs = self.svc.list_clubs()

        self.assertEqual(clubs[0]["league_count"], 2)
        self.assertEqual(clubs[0]["tournament_count"], 1)
        self.leagues.get_leagues_by_club.assert_called_once_with("a@club.com")

    def test_create_club_delegates_to_registration(self):
        payload = ClubSignup(clubName="Aces", email="a@club.com", password="Secret@123")
        self.svc.player_service.register_club = MagicMock()
        self.svc.player_service.register_club.return_value.model_dump.return_value = {"email": "a@club.com"}

        result = self.svc.create_club(payload)

        self.svc.player_service.register_club.assert_called_once_with(payload)
        self.assertEqual(result["email"], "a@club.com")

    def test_delete_club_404_when_not_a_club(self):
        self.players.find_player_by_email.return_value = {"role": "player"}
        with self.assertRaises(HTTPException) as ctx:
            self.svc.delete_club("p@x.com")
        self.assertEqual(ctx.exception.status_code, 404)
        self.players.delete_player_by_email.assert_not_called()

    def test_delete_club_removes_only_the_account(self):
        self.players.find_player_by_email.return_value = {"role": "admin", "email": "a@club.com"}
        self.svc.delete_club("a@club.com")
        self.players.delete_player_by_email.assert_called_once_with("a@club.com")
        # Orphan, not cascade: no league/tournament deletes.
        self.leagues.delete_league.assert_not_called()
        self.tournaments.delete_tournament.assert_not_called()

    # ---- players ------------------------------------------------------------

    def test_delete_player_purges_from_leagues_and_tournaments(self):
        self.players.find_player_by_email.return_value = {"role": "player", "email": "p@x.com"}
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
        self.players.count_by_role.return_value = {"admin": 2, "player": 40}
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
        self.players.count_by_role.return_value = {"admin": 1, "player": 1}
        self.leagues.get_all_leagues.return_value = []
        self.tournaments.get_all_tournaments.return_value = []
        self.audit.metrics.side_effect = RuntimeError("mongo down")

        m = self.svc.metrics()
        self.assertEqual(m["actions_24h"], 0)


if __name__ == "__main__":
    unittest.main()
