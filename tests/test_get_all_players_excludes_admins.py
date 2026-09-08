import unittest
from unittest.mock import MagicMock, patch

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


if __name__ == "__main__":
    unittest.main()
