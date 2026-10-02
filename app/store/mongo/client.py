"""One shared MongoClient for the pickleball stores.

Stores are constructed per request (and inside services), and each used to open
its own ``MongoClient`` - a fresh connection pool every time. ``MongoClient`` is
thread-safe and meant to be shared, so every store now gets the same instance
for a given URI.
"""
import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.server_api import ServerApi

PICKLEBALL_DB = "pickleball"


def get_client(mongo_uri: str | None = None) -> MongoClient:
    """The shared client for ``mongo_uri``, defaulting to ``$MONGO_URI``."""
    uri = mongo_uri or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI environment variable must be set")
    return _client_for(uri)


@lru_cache(maxsize=None)
def _client_for(uri: str) -> MongoClient:
    # Connecting is lazy: nothing touches the network until the first operation.
    return MongoClient(uri, server_api=ServerApi('1'))
