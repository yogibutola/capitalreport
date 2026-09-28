"""League and tournament rosters embed a copy of each player taken at
registration time, so paddles have to be joined in fresh at read time.

These tests pin that down from both ends: the join happens (paddles a player
added *after* registering still show up), and it happens *beside* the roster
rather than inside it (nothing folded into players[]/registrations[], which are
echoed back on the slotting and registration write paths).
"""
import unittest
from unittest.mock import MagicMock, patch

from app.services.pb_league_service import PBLeagueService
from app.services.pb_tournament_service import PBTournamentService
from app.store.mongo.pb_player_store import PBPlayerStore

PADDLES = [{"brand": "Joola", "model": "Perseus"}]


def roster_player(email, first="Bea", last="Baker"):
    """A roster copy as register_player writes it — note: no paddles key."""
    return {"firstName": first, "lastName": last, "email": email, "dupr_rating": 4.0}


class LeagueRosterPaddlesTest(unittest.TestCase):
    def setUp(self):
        self.mock_league_store = MagicMock()
        # PBLeagueService's constructor builds real stores; patch them all out.
        with patch('app.services.pb_league_service.PBMatchStore'), \
             patch('app.services.pb_league_service.PBPlayerStore'), \
             patch('app.services.pb_league_service.PBTournamentStore'), \
             patch('app.services.pb_league_service.PBTournamentService'):
            self.service = PBLeagueService(self.mock_league_store)

        self.service.pb_match_store = MagicMock()
        self.service.pb_match_store.get_match_details_by_league_id.return_value = []
        self.service.pb_player_store = MagicMock()
        self.service.pb_player_store.get_paddles_by_emails.return_value = {
            "bea@x.com": PADDLES,
        }

        self.league = {
            "_id": "league-1",
            "league_name": "Tuesday Ladder",
            "players": [roster_player("bea@x.com"), roster_player("cy@x.com", "Cy", "Chen")],
        }
        self.mock_league_store.get_league_details_by_league_name.return_value = self.league

    def get(self):
        return self.service.get_league_details_by_league_name("Tuesday Ladder")

    def test_the_roster_carries_a_fresh_paddle_map(self):
        """The embedded copies have no paddles; the map fills that gap."""
        result = self.get()
        self.assertEqual(result["paddles_by_email"], {"bea@x.com": PADDLES})

    def test_every_roster_email_is_looked_up(self):
        self.get()
        emails = self.service.pb_player_store.get_paddles_by_emails.call_args[0][0]
        self.assertCountEqual(emails, ["bea@x.com", "cy@x.com"])

    def test_only_one_lookup_is_issued_for_the_whole_roster(self):
        self.get()
        self.service.pb_player_store.get_paddles_by_emails.assert_called_once()

    def test_the_embedded_roster_copies_are_not_mutated(self):
        """players[] is echoed back on the slotting write. Anything merged into
        it here would be persisted onto the roster, so the join must stay beside
        it — this fails the moment someone 'simplifies' the side map away."""
        result = self.get()
        self.assertEqual(
            set(result["players"][0].keys()),
            {"firstName", "lastName", "email", "dupr_rating"},
        )

    def test_an_empty_roster_looks_up_nothing(self):
        self.league["players"] = []
        self.get()
        self.assertEqual(
            self.service.pb_player_store.get_paddles_by_emails.call_args[0][0], [])


class PaddleLookupStoreTest(unittest.TestCase):
    """The store method the joins depend on."""

    def setUp(self):
        self.store = PBPlayerStore(mongo_uri="mongodb://stub")
        self.collection = MagicMock()
        self.store.get_players_collection = lambda: self.collection

    def test_an_empty_roster_does_not_hit_mongo(self):
        self.assertEqual(self.store.get_paddles_by_emails([]), {})
        self.collection.find.assert_not_called()

    def test_emails_are_lowercased_on_the_way_in_and_out(self):
        self.collection.find.return_value = [
            {"email": "Bea@X.com", "paddles": PADDLES}]
        result = self.store.get_paddles_by_emails(["Bea@X.com"])
        self.assertEqual(self.collection.find.call_args[0][0],
                         {"email": {"$in": ["bea@x.com"]}})
        self.assertEqual(result, {"bea@x.com": PADDLES})

    def test_players_without_paddles_are_omitted(self):
        self.collection.find.return_value = [
            {"email": "bea@x.com", "paddles": PADDLES},
            {"email": "cy@x.com"},
            {"email": "dee@x.com", "paddles": []},
        ]
        result = self.store.get_paddles_by_emails(["bea@x.com", "cy@x.com", "dee@x.com"])
        self.assertEqual(result, {"bea@x.com": PADDLES})

    def test_the_password_hash_is_never_projected(self):
        self.collection.find.return_value = []
        self.store.get_paddles_by_emails(["bea@x.com"])
        self.assertEqual(self.collection.find.call_args[0][1], {"email": 1, "paddles": 1})


class TournamentRosterPaddlesTest(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.service = PBTournamentService(self.mock_store)
        self.doc = {
            "tournament_id": "t-1",
            "registrations": [
                {"firstName": "Bea", "lastName": "Baker", "email": "bea@x.com",
                 "partner_email": "pat@x.com"},
            ],
            "teams": [
                {"team_id": "tm-1", "player_one_email": "cy@x.com",
                 "player_two_email": "dee@x.com"},
            ],
        }
        self.mock_store.get_tournament_details.return_value = self.doc

    def looked_up(self):
        with patch('app.services.pb_tournament_service.PBPlayerStore') as store_cls:
            store_cls.return_value.get_paddles_by_emails.return_value = {}
            self.service.get_tournament_by_id("t-1")
            return store_cls.return_value.get_paddles_by_emails.call_args[0][0]

    def test_registrants_partners_and_both_team_halves_are_looked_up(self):
        """A doubles roster renders all of them, so all of them need paddles."""
        self.assertCountEqual(
            self.looked_up(), ["bea@x.com", "pat@x.com", "cy@x.com", "dee@x.com"])

    def test_a_missing_partner_does_not_become_a_none_lookup(self):
        self.doc["registrations"][0]["partner_email"] = None
        self.doc["teams"] = []
        self.assertCountEqual(self.looked_up(), ["bea@x.com"])

    def test_the_map_is_attached_to_the_document(self):
        with patch('app.services.pb_tournament_service.PBPlayerStore') as store_cls:
            store_cls.return_value.get_paddles_by_emails.return_value = {"bea@x.com": PADDLES}
            result = self.service.get_tournament_by_id("t-1")
        self.assertEqual(result["paddles_by_email"], {"bea@x.com": PADDLES})

    def test_the_registration_copies_are_not_mutated(self):
        with patch('app.services.pb_tournament_service.PBPlayerStore') as store_cls:
            store_cls.return_value.get_paddles_by_emails.return_value = {"bea@x.com": PADDLES}
            result = self.service.get_tournament_by_id("t-1")
        self.assertNotIn("paddles", result["registrations"][0])

    def test_a_missing_tournament_is_passed_through_untouched(self):
        self.mock_store.get_tournament_details.return_value = None
        with patch('app.services.pb_tournament_service.PBPlayerStore') as store_cls:
            self.assertIsNone(self.service.get_tournament_by_id("nope"))
            store_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
