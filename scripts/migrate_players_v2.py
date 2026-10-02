"""Migrate player profiles in ``pickleball.players`` to schema v2.

Plan and rationale: docs/schema/proposed-schema.md, section 3. In short:

  * Player accounts (``role != "admin"``) are kept, with the same ``_id``:
    ``password`` is renamed ``password_hash``, emails and names are trimmed and
    lowercased/normalised, timestamps and ``schema_version: 2`` are added, and
    the derived/club-only fields (``leagues``, ``role``, ``clubName``,
    ``address``, ``phone``, stray ``id``) are removed. Unknown fields are kept.
  * Club accounts (``role == "admin"``) are deleted - by decision, clubs are
    re-created in the new ``clubs`` collection. They remain in the backup.
  * Each player with a rating gets a ``rating_history`` row (source "migrated").

The default run is a DRY RUN: it only reads, then prints the pre-checks and the
planned changes. Nothing is written without ``--apply``.

Usage:
    export MONGO_URI=...
    mongodump --uri "$MONGO_URI" --db pickleball --out backup/pickleball-$(date +%F)   # first!
    python -m scripts.migrate_players_v2                         # dry run
    python -m scripts.migrate_players_v2 --apply --i-have-a-dump # migrate
    python -m scripts.migrate_players_v2 --rollback --backup players_backup_YYYYMMDD

Must ship together with the code that reads the v2 shape (``password_hash``, no
``role``) and the ``clubs`` collection - the current code cannot sign anyone in
against migrated documents.
"""
import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bson import ObjectId

from app.store.mongo.client import PICKLEBALL_DB, get_client
from app.store.mongo.schema.players import (
    PLAYERS_INDEXES,
    PLAYERS_VALIDATOR,
    RATING_HISTORY_INDEXES,
    SCHEMA_VERSION,
    player_v2_problems,
)

PLAYERS = "players"
RATING_HISTORY = "rating_history"

#: Every top-level field the current code writes to a player/club document.
KNOWN_FIELDS = {
    "_id", "email", "firstName", "lastName", "password", "dupr_rating", "role", "age",
    "state", "city", "zip_code", "paddles", "leagues", "clubName", "address", "phone",
    "reset_token_hash", "reset_token_expires", "is_demo", "id",
}
#: Fields v2 adds. A document that already has them was migrated by an earlier run.
V2_FIELDS = {"password_hash", "created_at", "updated_at", "deleted_at", "schema_version"}
CLUB_FIELDS = ("clubName", "address", "phone")
#: Removed from every migrated player (``password`` is renamed, not dropped).
REMOVED_FIELDS = ("password", "role", "leagues", "clubName", "address", "phone", "id")


def is_club(doc: dict) -> bool:
    return doc.get("role") == "admin"


def is_migrated(doc: dict) -> bool:
    return doc.get("schema_version") == SCHEMA_VERSION


def normalize_email(email) -> str | None:
    return email.strip().lower() if isinstance(email, str) else None


def _utcnow_naive() -> datetime:
    # pymongo hands back naive datetimes that mean UTC (tz_aware=False), which is
    # also how reset_token_expires is written today - compare like with like.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------

@dataclass
class PrecheckReport:
    players: int = 0
    clubs: int = 0
    already_migrated: int = 0
    #: Must be fixed by hand before --apply will run.
    blocking: list[str] = field(default_factory=list)
    #: Worth reading, but the migration handles them.
    warnings: list[str] = field(default_factory=list)
    #: Unknown top-level field -> how many player docs carry it (kept as-is).
    unknown_fields: dict[str, int] = field(default_factory=dict)
    #: Non-empty club-only values found on player docs; recorded before removal.
    club_field_values: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocking


def precheck(docs: list[dict]) -> PrecheckReport:
    """Check every document can be migrated without loss or rejection."""
    report = PrecheckReport()
    players = [d for d in docs if not is_club(d)]
    report.players = len(players)
    report.clubs = len(docs) - len(players)
    report.already_migrated = sum(1 for d in players if is_migrated(d))

    # Duplicates among players, after the same normalisation the migration applies.
    by_email: dict[str, list] = {}
    for d in players:
        email = normalize_email(d.get("email"))
        if email:
            by_email.setdefault(email, []).append(d["_id"])
    for email, ids in by_email.items():
        if len(ids) > 1:
            report.blocking.append(f"duplicate email {email}: {', '.join(map(str, ids))}")

    club_emails = {normalize_email(d.get("email")) for d in docs if is_club(d)}
    for email in sorted(set(by_email) & club_emails - {None}):
        report.warnings.append(f"{email} is both a player and a club; the club account will be deleted")

    unknown = Counter()
    for d in players:
        _id = d["_id"]
        if not isinstance(_id, ObjectId):
            report.warnings.append(f"{_id!r}: _id is not an ObjectId; created_at will be the migration time")
        # Validate the document as it WILL look, so the strict validator can't
        # reject it afterwards. Already-migrated docs are checked as they are.
        candidate = d if is_migrated(d) else migrated_view(d, _utcnow_naive())
        for problem in player_v2_problems(candidate):
            report.blocking.append(f"{_id}: {problem}")
        unknown.update(k for k in d if k not in KNOWN_FIELDS | V2_FIELDS)
        values = {k: d[k] for k in CLUB_FIELDS if d.get(k) not in (None, "")}
        if values:
            report.club_field_values.append({"_id": str(_id), "email": d.get("email"), **values})
    report.unknown_fields = dict(unknown)
    if unknown:
        report.warnings.append(f"unknown fields carried over unchanged: {dict(unknown)}")
    if report.club_field_values:
        report.warnings.append(
            f"{len(report.club_field_values)} player(s) have club-only values that will be "
            "removed (listed in club_field_values; also kept in the backup)")
    return report


# ---------------------------------------------------------------------------
# Per-document transform (pure)
# ---------------------------------------------------------------------------

def plan_update(doc: dict, now: datetime) -> tuple[dict, list[str]] | None:
    """The ``($set, $unset)`` that migrates one player doc, or None if there's nothing to do.

    ``now`` is naive UTC. Pure: never touches the database.
    """
    if is_club(doc) or is_migrated(doc):
        return None
    to_set = {
        "email": normalize_email(doc.get("email")),
        "password_hash": doc.get("password"),
        "firstName": doc["firstName"].strip() if isinstance(doc.get("firstName"), str) else doc.get("firstName"),
        "lastName": doc["lastName"].strip() if isinstance(doc.get("lastName"), str) else doc.get("lastName"),
        "paddles": doc.get("paddles") if doc.get("paddles") is not None else [],
        "is_demo": bool(doc.get("is_demo", False)),
        # An ObjectId records when it was minted - the best "joined" date we have.
        "created_at": _naive(doc["_id"].generation_time) if isinstance(doc["_id"], ObjectId) else now,
        "updated_at": now,
        "deleted_at": None,
        "schema_version": SCHEMA_VERSION,
    }
    to_unset = [f for f in REMOVED_FIELDS if f in doc]
    expires = doc.get("reset_token_expires")
    if expires is not None and isinstance(expires, datetime) and _naive(expires) <= now:
        to_unset += [f for f in ("reset_token_hash", "reset_token_expires") if f in doc]
    return to_set, to_unset


def migrated_view(doc: dict, now: datetime) -> dict:
    """``doc`` as it will look after migration (used by pre-checks and dry runs)."""
    plan = plan_update(doc, now)
    if plan is None:
        return dict(doc)
    to_set, to_unset = plan
    out = {k: v for k, v in doc.items() if k not in to_unset}
    out.update(to_set)
    return out


# ---------------------------------------------------------------------------
# Post-migration verification (pure)
# ---------------------------------------------------------------------------

#: Field -> how the old value must map to the new one.
_PRESERVED = {
    "email": normalize_email,
    "firstName": lambda v: v.strip() if isinstance(v, str) else v,
    "lastName": lambda v: v.strip() if isinstance(v, str) else v,
    "dupr_rating": lambda v: v,
    "age": lambda v: v,
    "state": lambda v: v,
    "city": lambda v: v,
    "zip_code": lambda v: v,
    "paddles": lambda v: v if v is not None else [],
    "is_demo": lambda v: bool(v) if v is not None else False,
}


def verify(backup_docs: list[dict], current_docs: list[dict]) -> list[str]:
    """Problems found comparing the migrated collection with its backup; empty means good.

    Every backed-up player must be present under the same ``_id`` with every
    preserved field intact, the password hash moved unchanged, the removed fields
    gone, unknown fields untouched, and the document valid under v2. No club and
    no unexpected document may remain.
    """
    problems = []
    old_players = {d["_id"]: d for d in backup_docs if not is_club(d)}
    current = {d["_id"]: d for d in current_docs}

    if len(current) != len(old_players):
        problems.append(f"expected {len(old_players)} players, found {len(current)}")
    for _id in sorted(set(old_players) - set(current), key=str):
        problems.append(f"{_id}: missing after migration")
    for _id in sorted(set(current) - set(old_players), key=str):
        problems.append(f"{_id}: not in the backup as a player")

    for _id, old in old_players.items():
        new = current.get(_id)
        if new is None:
            continue
        if is_migrated(old):
            # Migrated by an earlier run: it must simply be unchanged.
            if new != old:
                problems.append(f"{_id}: already-migrated document was modified")
            continue
        for f, expected in _PRESERVED.items():
            if new.get(f) != expected(old.get(f)):
                problems.append(f"{_id}: {f} changed ({old.get(f)!r} -> {new.get(f)!r})")
        if new.get("password_hash") != old.get("password"):
            problems.append(f"{_id}: password hash not carried over")
        for f in REMOVED_FIELDS:
            if f in new:
                problems.append(f"{_id}: {f} still present")
        for f in set(old) - KNOWN_FIELDS - V2_FIELDS:
            if new.get(f) != old[f]:
                problems.append(f"{_id}: unknown field {f} was not carried over unchanged")
        old_expiry = old.get("reset_token_expires")
        if old.get("reset_token_hash") and new.get("reset_token_hash") not in (None, old["reset_token_hash"]):
            problems.append(f"{_id}: reset token changed")
        if new.get("reset_token_hash") and old_expiry is not None and new.get("reset_token_expires") != old_expiry:
            problems.append(f"{_id}: reset token expiry changed")
        problems += [f"{_id}: {p}" for p in player_v2_problems(new)]
    return problems


def rating_history_rows(players: list[dict], now: datetime) -> list[dict]:
    """One "migrated" rating row per player that has a rating."""
    return [
        {"player_id": p["_id"], "rating": p["dupr_rating"], "source": "migrated", "recorded_at": now}
        for p in players
        if not is_club(p) and p.get("dupr_rating") is not None
    ]


# ---------------------------------------------------------------------------
# Database steps
# ---------------------------------------------------------------------------

class MigrationError(RuntimeError):
    pass


def default_backup_name(now: datetime) -> str:
    return f"players_backup_{now:%Y%m%d}"


def backup(db, name: str) -> int:
    """Copy ``players`` to ``name`` in the same database; refuses to overwrite."""
    if name in db.list_collection_names():
        raise MigrationError(f"backup collection {name} already exists; pick another --backup name")
    db[PLAYERS].aggregate([{"$match": {}}, {"$out": name}])
    copied, source = db[name].count_documents({}), db[PLAYERS].count_documents({})
    if copied != source:
        raise MigrationError(f"backup {name} has {copied} documents, players has {source}")
    return copied


def apply(db, backup_name: str, now: datetime | None = None, log=print) -> None:
    """Run the migration. Stops (leaving the backup in place) at the first failed check."""
    now = now or _utcnow_naive()
    docs = list(db[PLAYERS].find())
    report = precheck(docs)
    if not report.ok:
        raise MigrationError("pre-checks failed:\n  " + "\n  ".join(report.blocking))

    log(f"Backing up {len(docs)} documents to {backup_name} ...")
    backup(db, backup_name)

    migrated = 0
    for doc in docs:
        plan = plan_update(doc, now)
        if plan is None:
            continue
        to_set, to_unset = plan
        update = {"$set": to_set}
        if to_unset:
            update["$unset"] = {f: "" for f in to_unset}
        db[PLAYERS].update_one({"_id": doc["_id"]}, update)
        migrated += 1
    log(f"Migrated {migrated} player documents ({report.already_migrated} were already on v2).")

    rows = rating_history_rows([d for d in docs if not is_migrated(d)], now)
    for row in rows:
        # Upsert keyed on (player, source) so a re-run never duplicates history.
        db[RATING_HISTORY].update_one(
            {"player_id": row["player_id"], "source": "migrated"}, {"$setOnInsert": row}, upsert=True)
    db[RATING_HISTORY].create_indexes(RATING_HISTORY_INDEXES)
    log(f"Seeded rating_history for {len(rows)} players.")

    deleted = db[PLAYERS].delete_many({"role": "admin"}).deleted_count
    log(f"Deleted {deleted} club accounts (kept in {backup_name}).")

    db[PLAYERS].create_indexes(PLAYERS_INDEXES)
    db.command("collMod", PLAYERS, validator=PLAYERS_VALIDATOR,
               validationLevel="moderate", validationAction="error")

    problems = verify(list(db[backup_name].find()), list(db[PLAYERS].find()))
    expected_rows = sum(1 for d in docs if not is_club(d) and d.get("dupr_rating") is not None)
    if db[RATING_HISTORY].count_documents({"source": "migrated"}) != expected_rows:
        problems.append(f"rating_history should have {expected_rows} migrated rows")
    if problems:
        raise MigrationError(
            f"post-checks failed - roll back with --rollback --backup {backup_name}:\n  "
            + "\n  ".join(problems))

    db.command("collMod", PLAYERS, validationLevel="strict")
    log("Post-checks passed; validator is now strict.")


def rollback(db, backup_name: str, log=print) -> None:
    """Put the backup back as ``players``. ``rating_history`` rows from the run are removed."""
    if backup_name not in db.list_collection_names():
        raise MigrationError(f"no backup collection named {backup_name}")
    db[PLAYERS].drop()
    db[backup_name].rename(PLAYERS)
    removed = db[RATING_HISTORY].delete_many({"source": "migrated"}).deleted_count
    log(f"Restored players from {backup_name}; removed {removed} migrated rating_history rows.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(report: PrecheckReport, docs: list[dict], now: datetime) -> None:
    print(f"players: {report.players}  (already on v2: {report.already_migrated})")
    print(f"clubs to delete: {report.clubs}")
    for w in report.warnings:
        print(f"WARNING: {w}")
    for row in report.club_field_values:
        print(f"  club-only values on player: {row}")
    for b in report.blocking:
        print(f"BLOCKING: {b}")
    planned = [(d, plan_update(d, now)) for d in docs]
    planned = [(d, p) for d, p in planned if p]
    print(f"\n{len(planned)} player document(s) would be updated. First few:")
    for d, (to_set, to_unset) in planned[:5]:
        shown = {k: ("<hash>" if k == "password_hash" else v) for k, v in to_set.items()}
        print(f"  {d['_id']}: set {shown}; unset {to_unset}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write changes (default is a read-only dry run)")
    mode.add_argument("--rollback", action="store_true", help="restore players from --backup")
    parser.add_argument("--i-have-a-dump", action="store_true",
                        help="confirm a mongodump of the pickleball DB exists (required with --apply)")
    parser.add_argument("--backup", help="in-database backup collection name (default players_backup_YYYYMMDD)")
    parser.add_argument("--db", default=PICKLEBALL_DB)
    args = parser.parse_args(argv)

    db = get_client()[args.db]
    now = _utcnow_naive()
    backup_name = args.backup or default_backup_name(now)

    try:
        if args.rollback:
            if not args.backup:
                parser.error("--rollback needs --backup <collection name>")
            rollback(db, backup_name)
            return 0
        if args.apply:
            if not args.i_have_a_dump:
                parser.error("--apply needs --i-have-a-dump: take a mongodump first (see --help)")
            apply(db, backup_name, now)
            return 0
        docs = list(db[PLAYERS].find())
        report = precheck(docs)
        _print_report(report, docs, now)
        print("\nDRY RUN - nothing was written." + ("" if report.ok else " Fix the BLOCKING items before --apply."))
        return 0 if report.ok else 1
    except MigrationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
