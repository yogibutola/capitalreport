import unittest
from unittest.mock import MagicMock, patch

from app.services.pb_tournament_service import AccountExistsError, PBTournamentService
from app.vo.pb.tournament_registration_payload import PublicTournamentRegistrationPayload


def _pending_tournament(**overrides):
    doc = {
        "tournament_id": "T1",
        "tournament_name": "Spring Open",
        "tournament_status": "pending",
        "match_format": "doubles",
        "dupr_min": 2.5,
        "dupr_max": 5.0,
        "registrations": [],
    }
    doc.update(overrides)
    return doc


def _payload(**overrides):
    data = {
        "tournament_id": "T1",
        "firstName": "New",
        "lastName": "Player",
        "email": "New.Player@example.com",
        "password": "Sup3r@Pass",
        "dupr_rating": 3.5,
        "needs_partner": True,
    }
    data.update(overrides)
    return PublicTournamentRegistrationPayload(**data)


class TestPublicTournamentRegistration(unittest.TestCase):
    def setUp(self):
        self.tournament_store = MagicMock()
        self.service = PBTournamentService(self.tournament_store)

        # A stateful in-memory player store shared by every PBPlayerStore() call.
        self._players: dict[str, dict] = {}

        def find_by_email(email):
            return self._players.get((email or "").lower())

        def create_player(data):
            doc = {**data, "_id": "pid-1"}
            self._players[data["email"].lower()] = doc
            return doc

        self.player_store = MagicMock()
        self.player_store.find_player_by_email.side_effect = find_by_email
        self.player_store.create_player.side_effect = create_player

        patcher = patch(
            "app.services.pb_tournament_service.PBPlayerStore",
            return_value=self.player_store,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_creates_account_and_registers(self):
        self.tournament_store.get_tournament_details.return_value = _pending_tournament()

        result = self.service.register_public(_payload())

        # Account created with the lowercased email.
        self.assertIn("new.player@example.com", self._players)
        # Registration persisted back to the tournament.
        self.tournament_store.update_tournament.assert_called()
        saved = self.tournament_store.update_tournament.call_args[0][1]
        self.assertEqual(len(saved["registrations"]), 1)
        self.assertTrue(saved["registrations"][0]["needs_partner"])
        # Caller gets a session token back.
        self.assertTrue(result["token"])
        self.assertEqual(result["email"], "new.player@example.com")

    def test_existing_account_is_rejected(self):
        self._players["new.player@example.com"] = {"email": "new.player@example.com"}
        self.tournament_store.get_tournament_details.return_value = _pending_tournament()

        with self.assertRaises(AccountExistsError):
            self.service.register_public(_payload())
        self.tournament_store.update_tournament.assert_not_called()

    def test_closed_registration_is_rejected(self):
        self.tournament_store.get_tournament_details.return_value = _pending_tournament(
            tournament_status="active"
        )

        with self.assertRaises(ValueError):
            self.service.register_public(_payload())
        self.player_store.create_player.assert_not_called()

    def test_dupr_out_of_range_rejected_before_account_creation(self):
        self.tournament_store.get_tournament_details.return_value = _pending_tournament()

        with self.assertRaises(ValueError):
            self.service.register_public(_payload(dupr_rating=6.0))
        self.player_store.create_player.assert_not_called()

    def test_missing_tournament_is_rejected(self):
        self.tournament_store.get_tournament_details.return_value = None

        with self.assertRaises(ValueError):
            self.service.register_public(_payload())

    def test_invite_partner_by_email(self):
        self.tournament_store.get_tournament_details.return_value = _pending_tournament()

        self.service.register_public(
            _payload(
                needs_partner=False,
                partner_invite_name="Sam Partner",
                partner_invite_email="sam@example.com",
            )
        )

        saved = self.tournament_store.update_tournament.call_args[0][1]
        reg = saved["registrations"][0]
        self.assertEqual(reg["partner_email"], "sam@example.com")
        self.assertFalse(reg["partner_registered"])


if __name__ == "__main__":
    unittest.main()
