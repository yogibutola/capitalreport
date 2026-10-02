"""Schema v2 for the ``players`` collection - the one collection whose data is
preserved across the redesign (see docs/schema/proposed-schema.md).

``PLAYERS_VALIDATOR`` is the MongoDB ``$jsonSchema`` applied after migration;
``player_v2_problems`` is the same rule set in Python, so the migration can check
every document *before* the database would reject it. Keep the two in step:
tests/test_players_schema.py cross-checks them field by field.
"""
import re
from datetime import datetime

from pymongo import ASCENDING, DESCENDING, IndexModel

SCHEMA_VERSION = 2
MAX_PADDLES = 3

EMAIL_PATTERN = r"^[^\sA-Z@]+@[^\sA-Z@]+$"  # lowercased, no whitespace
ZIP_PATTERN = r"^\d{5}$"

PLAYERS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "email", "password_hash", "firstName", "lastName", "paddles",
            "is_demo", "created_at", "updated_at", "schema_version",
        ],
        "properties": {
            "email": {"bsonType": "string", "pattern": EMAIL_PATTERN},
            "password_hash": {"bsonType": "string", "minLength": 1},
            "firstName": {"bsonType": "string", "minLength": 1},
            "lastName": {"bsonType": "string", "minLength": 1},
            "dupr_rating": {"bsonType": ["double", "int", "null"], "minimum": 0, "maximum": 8},
            "age": {"bsonType": ["int", "null"], "minimum": 13, "maximum": 120},
            "state": {"bsonType": ["string", "null"], "maxLength": 100},
            "city": {"bsonType": ["string", "null"], "maxLength": 100},
            "zip_code": {"bsonType": ["string", "null"], "pattern": ZIP_PATTERN},
            "paddles": {
                "bsonType": "array",
                "maxItems": MAX_PADDLES,
                "items": {
                    "bsonType": "object",
                    "required": ["brand"],
                    "properties": {
                        "brand": {"bsonType": "string", "minLength": 1, "maxLength": 40},
                        "model": {"bsonType": ["string", "null"], "maxLength": 60},
                    },
                },
            },
            "reset_token_hash": {"bsonType": ["string", "null"]},
            "reset_token_expires": {"bsonType": ["date", "null"]},
            "is_demo": {"bsonType": "bool"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
            "deleted_at": {"bsonType": ["date", "null"]},
            "schema_version": {"bsonType": "int", "enum": [SCHEMA_VERSION]},
        },
        # Deliberately no additionalProperties: false. Fields we don't know about
        # are carried over by the migration, never silently dropped.
    }
}

PLAYERS_INDEXES = [
    IndexModel([("email", ASCENDING)], unique=True, name="email_unique"),
    IndexModel([("reset_token_hash", ASCENDING)], sparse=True, name="reset_token_hash"),
    IndexModel([("lastName", ASCENDING), ("firstName", ASCENDING)], name="name"),
    IndexModel([("dupr_rating", ASCENDING)], name="dupr_rating"),
]

RATING_HISTORY_INDEXES = [
    IndexModel([("player_id", ASCENDING), ("recorded_at", DESCENDING)], name="player_recent"),
]


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _string_or_none(doc: dict, field: str, problems: list, max_len: int | None = None,
                    pattern: str | None = None) -> None:
    v = doc.get(field)
    if v is None:
        return
    if not isinstance(v, str):
        problems.append(f"{field} is not a string")
    elif max_len is not None and len(v) > max_len:
        problems.append(f"{field} is longer than {max_len} characters")
    elif pattern is not None and not re.match(pattern, v):
        problems.append(f"{field} {v!r} does not match {pattern}")


def paddle_problems(paddles) -> list[str]:
    """What's wrong with a ``paddles`` value under v2 rules (null is not allowed)."""
    if not isinstance(paddles, list):
        return ["paddles is not a list"]
    problems = []
    if len(paddles) > MAX_PADDLES:
        problems.append(f"more than {MAX_PADDLES} paddles")
    for i, p in enumerate(paddles):
        if not isinstance(p, dict):
            problems.append(f"paddles[{i}] is not an object")
            continue
        brand, model = p.get("brand"), p.get("model")
        if not isinstance(brand, str) or not 1 <= len(brand) <= 40:
            problems.append(f"paddles[{i}].brand must be 1-40 characters")
        if model is not None and (not isinstance(model, str) or len(model) > 60):
            problems.append(f"paddles[{i}].model must be at most 60 characters")
    return problems


def player_v2_problems(doc: dict) -> list[str]:
    """Every way ``doc`` would fail ``PLAYERS_VALIDATOR``; empty means valid."""
    problems = []
    required = PLAYERS_VALIDATOR["$jsonSchema"]["required"]
    problems += [f"missing {f}" for f in required if doc.get(f) is None]

    email = doc.get("email")
    if email is not None and (not isinstance(email, str) or not re.match(EMAIL_PATTERN, email)):
        problems.append(f"email {email!r} is not a lowercased address")
    for field in ("password_hash", "firstName", "lastName"):
        v = doc.get(field)
        if v is not None and (not isinstance(v, str) or not v):
            problems.append(f"{field} must be a non-empty string")

    rating = doc.get("dupr_rating")
    if rating is not None and (not _is_number(rating) or not 0 <= rating <= 8):
        problems.append(f"dupr_rating {rating!r} is not a number between 0 and 8")
    age = doc.get("age")
    if age is not None and (not _is_int(age) or not 13 <= age <= 120):
        problems.append(f"age {age!r} is not a whole number between 13 and 120")

    _string_or_none(doc, "state", problems, max_len=100)
    _string_or_none(doc, "city", problems, max_len=100)
    _string_or_none(doc, "zip_code", problems, pattern=ZIP_PATTERN)
    _string_or_none(doc, "reset_token_hash", problems)

    if doc.get("paddles") is not None:
        problems += paddle_problems(doc["paddles"])

    for field in ("reset_token_expires", "deleted_at"):
        v = doc.get(field)
        if v is not None and not isinstance(v, datetime):
            problems.append(f"{field} is not a date")
    for field in ("created_at", "updated_at"):
        v = doc.get(field)
        if v is not None and not isinstance(v, datetime):
            problems.append(f"{field} is not a date")
    if doc.get("is_demo") is not None and not isinstance(doc["is_demo"], bool):
        problems.append("is_demo is not a boolean")
    if doc.get("schema_version") is not None and doc["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version is not {SCHEMA_VERSION}")
    return problems
