import os
import unittest
from unittest.mock import patch

from app.store.mongo.client import get_client
from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_player_store import PBPlayerStore

URI = "mongodb://localhost:27017/?directConnection=true"


class TestSharedClient(unittest.TestCase):
    def test_same_uri_gives_the_same_client(self):
        self.assertIs(get_client(URI), get_client(URI))

    def test_stores_share_one_client(self):
        with patch.dict(os.environ, {"MONGO_URI": URI}):
            self.assertIs(PBPlayerStore().client, PBLeagueStore().client)
            self.assertIs(PBPlayerStore().client, get_client())

    def test_missing_uri_is_still_a_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                get_client()


if __name__ == "__main__":
    unittest.main()
