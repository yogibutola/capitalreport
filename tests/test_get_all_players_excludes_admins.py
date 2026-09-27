import unittest
from unittest.mock import MagicMock, patch

from app.services.pb_player_service import PBPlayerService
from app.store.mongo.pb_player_store import PBPlayerStore


class TestGetAllPlayersExcludesAdmins(unittest.TestCase):
    """Club (admin) accounts share the players collection; they must never be
    returned by get_all_players(), which feeds every player list / picker."""

    def _store(self, docs):
        collection = MagicMock()
        collection.find.return_value = list(docs)
        store = PBPlayerStore.__new__(PBPlayerStore)  # skip __init__ (no Mongo)
        store.get_players_collection = MagicMock(return_value=collection)
        return store, collection

    def test_query_filters_out_admin_role(self):
        store, collection = self._store([
            {"_id": 1, "email": "player@example.com", "role": "player"},
        ])
        store.get_all_players()
        collection.find.assert_called_once_with({"role": {"$ne": "admin"}})

    def test_ids_are_stringified(self):
        store, _ = self._store([{"_id": 42, "email": "p@example.com", "role": "player"}])
        result = store.get_all_players()
        self.assertEqual(result[0]["_id"], "42")


class TestFindPlayersQuery(unittest.TestCase):
    """find_players builds the search query. Distance isn't in here - Mongo has no
    coordinates - but names and ratings are, so they don't get filtered in Python."""

    def _store(self, docs=()):
        collection = MagicMock()
        collection.find.return_value = list(docs)
        store = PBPlayerStore.__new__(PBPlayerStore)  # skip __init__ (no Mongo)
        store.get_players_collection = MagicMock(return_value=collection)
        return store, collection

    def _query(self, **kwargs):
        store, collection = self._store()
        store.find_players(**kwargs)
        return collection.find.call_args[0][0]

    def test_admins_are_always_excluded(self):
        self.assertEqual(self._query()["role"], {"$ne": "admin"})

    def test_names_match_case_insensitive_substrings(self):
        query = self._query(first_name="bea", last_name="bak")
        self.assertEqual(query["firstName"], {"$regex": "bea", "$options": "i"})
        self.assertEqual(query["lastName"], {"$regex": "bak", "$options": "i"})

    def test_regex_metacharacters_in_a_name_are_matched_literally(self):
        """Someone searching "a.b" shouldn't get every three-letter name."""
        self.assertEqual(self._query(first_name="a.b")["firstName"]["$regex"], r"a\.b")

    def test_both_dupr_bounds(self):
        self.assertEqual(self._query(dupr_min=3.0, dupr_max=4.0)["dupr_rating"],
                         {"$gte": 3.0, "$lte": 4.0})

    def test_only_the_supplied_dupr_bound_is_applied(self):
        self.assertEqual(self._query(dupr_min=3.0)["dupr_rating"], {"$gte": 3.0})
        self.assertEqual(self._query(dupr_max=4.0)["dupr_rating"], {"$lte": 4.0})

    def test_no_dupr_filter_leaves_the_field_out(self):
        """A rating filter would exclude unrated players, so it must not appear
        unless the caller actually asked for a band."""
        self.assertNotIn("dupr_rating", self._query())

    def test_the_searcher_is_excluded_by_lowercased_email(self):
        self.assertEqual(self._query(exclude_email="Me@Example.com")["email"],
                         {"$ne": "me@example.com"})

    def test_the_password_hash_is_never_projected(self):
        store, collection = self._store()
        store.find_players()
        projection = collection.find.call_args[0][1]
        self.assertNotIn("password", projection)
        for field in ("firstName", "lastName", "email", "dupr_rating", "city", "state", "zip_code"):
            self.assertEqual(projection[field], 1, field)

    def test_ids_are_stringified(self):
        store, _ = self._store([{"_id": 7, "email": "p@example.com"}])
        self.assertEqual(store.find_players()[0]["_id"], "7")


class TestGetAllPlayersToleratesMissingRating(unittest.TestCase):
    """A seeded or legacy document without dupr_rating used to raise a KeyError
    here, 500ing the whole listing for every caller."""

    def test_a_rating_less_player_is_returned_with_a_null_rating(self):
        mock_store = MagicMock()
        mock_store.get_all_players.return_value = [
            {"_id": "1", "firstName": "Ada", "lastName": "Lovelace",
             "email": "ada@example.com", "role": "player"},  # no dupr_rating
        ]
        service = PBPlayerService(mock_store)

        result = service.get_all_players()

        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].dupr_rating)


if __name__ == "__main__":
    unittest.main()
