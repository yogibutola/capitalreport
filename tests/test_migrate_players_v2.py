"""scripts/migrate_players_v2.py: pre-checks, the per-document transform,
post-verification, and apply/rollback end-to-end against an in-memory database.
"""
import copy
import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from unittest.mock import patch

from bson import ObjectId

from app.store.mongo.schema.players import player_v2_problems
from scripts import migrate_players_v2 as mig

NOW = datetime(2026, 10, 2, 12, 0)


# ---------------------------------------------------------------------------
# A tiny in-memory stand-in for the handful of pymongo calls the script makes.
# ---------------------------------------------------------------------------

def _matches(doc, flt):
    return all(doc.get(k) == v for k, v in (flt or {}).items())


class _Result:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self, db, name):
        self.db, self.name = db, name

    @property
    def docs(self):
        return self.db.data.setdefault(self.name, [])

    def find(self, flt=None):
        return [copy.deepcopy(d) for d in self.db.data.get(self.name, []) if _matches(d, flt)]

    def count_documents(self, flt):
        return len(self.find(flt))

    def update_one(self, flt, update, upsert=False):
        self.db.writes += 1
        for d in self.docs:
            if _matches(d, flt):
                d.update(copy.deepcopy(update.get("$set", {})))
                for f in update.get("$unset", {}):
                    d.pop(f, None)
                return
        if upsert:
            new = dict(flt)
            new.update(copy.deepcopy(update.get("$setOnInsert", {})))
            self.docs.append(new)

    def delete_many(self, flt):
        self.db.writes += 1
        keep = [d for d in self.docs if not _matches(d, flt)]
        removed = len(self.docs) - len(keep)
        self.db.data[self.name] = keep
        return _Result(removed)

    def aggregate(self, pipeline):
        self.db.writes += 1
        (out,) = [stage["$out"] for stage in pipeline if "$out" in stage]
        self.db.data[out] = self.find()

    def create_indexes(self, models):
        self.db.writes += 1
        self.db.indexes.setdefault(self.name, []).extend(m.document["name"] for m in models)
        for m in models:
            if m.document.get("unique"):
                field = next(iter(m.document["key"]))
                values = [d.get(field) for d in self.docs]
                assert len(values) == len(set(values)), f"duplicate {field}"

    def drop(self):
        self.db.writes += 1
        self.db.data.pop(self.name, None)

    def rename(self, new_name):
        self.db.writes += 1
        self.db.data[new_name] = self.db.data.pop(self.name)


class FakeDB:
    def __init__(self, players):
        self.data = {"players": copy.deepcopy(players)}
        self.indexes, self.commands, self.writes = {}, [], 0

    def __getitem__(self, name):
        return FakeCollection(self, name)

    def list_collection_names(self):
        return list(self.data)

    def command(self, *args, **kwargs):
        self.writes += 1
        self.commands.append((args, kwargs))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def player(**overrides):
    doc = {
        "_id": ObjectId(), "email": "pat@example.com", "firstName": "Pat", "lastName": "Lee",
        "password": "$2b$12$pat", "dupr_rating": 3.5, "role": "player", "age": None,
        "state": "OR", "city": "Portland", "zip_code": "97205", "paddles": [],
        "leagues": [{"league_id": "x", "league_name": "Tuesday"}],
        "clubName": None, "address": None, "phone": None,
    }
    doc.update(overrides)
    return doc


def club(**overrides):
    doc = {
        "_id": ObjectId(), "email": "club@example.com", "firstName": "Baseline Club",
        "lastName": "Admin", "password": "$2b$12$club", "dupr_rating": 0.0, "role": "admin",
        "clubName": "Baseline Club", "address": "1 Court St", "phone": "555", "leagues": [],
    }
    doc.update(overrides)
    return doc


def realistic_population():
    return [
        player(),
        # Legacy shapes: no role, mixed-case email, padded names, null paddles,
        # no paddles key at all, an unknown field, demo flag.
        player(email=" Sam@Example.COM ", firstName=" Sam ", lastName="Ng ", paddles=None,
               dupr_rating=None, is_demo=True, favourite_court="3"),
        {k: v for k, v in player(email="lee@example.com", firstName="Lee").items()
         if k not in ("role", "paddles", "clubName", "address", "phone")},
        # Live and expired password resets.
        player(email="reset@example.com", reset_token_hash="live",
               reset_token_expires=NOW + timedelta(minutes=10)),
        player(email="stale@example.com", reset_token_hash="old",
               reset_token_expires=NOW - timedelta(days=1)),
        player(email="paddles@example.com", paddles=[{"brand": "Selkirk", "model": "Vanguard"}], age=52),
        club(),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPlanUpdate(unittest.TestCase):
    def test_field_mapping(self):
        doc = player(email=" Pat@Example.com ", firstName=" Pat ", paddles=None, id="stray")
        to_set, to_unset = mig.plan_update(doc, NOW)
        self.assertEqual(to_set["email"], "pat@example.com")
        self.assertEqual(to_set["password_hash"], "$2b$12$pat")
        self.assertEqual(to_set["firstName"], "Pat")
        self.assertEqual(to_set["paddles"], [])
        self.assertIs(to_set["is_demo"], False)
        self.assertEqual(to_set["created_at"], doc["_id"].generation_time.replace(tzinfo=None))
        self.assertEqual(to_set["updated_at"], NOW)
        self.assertIsNone(to_set["deleted_at"])
        self.assertEqual(to_set["schema_version"], 2)
        self.assertEqual(set(to_unset), {"password", "role", "leagues", "clubName", "address", "phone", "id"})

    def test_preserved_values_are_not_touched(self):
        doc = player(dupr_rating=4.25, age=60, paddles=[{"brand": "JOOLA", "model": None}])
        to_set, _ = mig.plan_update(doc, NOW)
        view = mig.migrated_view(doc, NOW)
        for f in ("dupr_rating", "age", "state", "city", "zip_code"):
            self.assertEqual(view[f], doc[f])
            self.assertNotIn(f, to_set)
        self.assertEqual(view["paddles"], doc["paddles"])

    def test_only_fields_that_exist_are_unset(self):
        doc = {k: v for k, v in player().items() if k not in ("clubName", "address", "phone")}
        _, to_unset = mig.plan_update(doc, NOW)
        self.assertEqual(set(to_unset), {"password", "role", "leagues"})

    def test_unknown_fields_are_kept(self):
        view = mig.migrated_view(player(favourite_court="3"), NOW)
        self.assertEqual(view["favourite_court"], "3")

    def test_expired_reset_token_is_dropped_live_one_kept(self):
        _, unset = mig.plan_update(player(reset_token_hash="h", reset_token_expires=NOW - timedelta(seconds=1)), NOW)
        self.assertIn("reset_token_hash", unset)
        self.assertIn("reset_token_expires", unset)
        _, unset = mig.plan_update(player(reset_token_hash="h", reset_token_expires=NOW + timedelta(minutes=5)), NOW)
        self.assertNotIn("reset_token_hash", unset)

    def test_clubs_and_already_migrated_docs_are_skipped(self):
        self.assertIsNone(mig.plan_update(club(), NOW))
        migrated = mig.migrated_view(player(), NOW)
        self.assertIsNone(mig.plan_update(migrated, NOW))

    def test_every_realistic_player_migrates_to_a_valid_v2_doc(self):
        for doc in realistic_population():
            if mig.is_club(doc):
                continue
            with self.subTest(email=doc["email"]):
                self.assertEqual(player_v2_problems(mig.migrated_view(doc, NOW)), [])


class TestPrecheck(unittest.TestCase):
    def test_clean_population_passes(self):
        report = mig.precheck(realistic_population())
        self.assertTrue(report.ok, report.blocking)
        self.assertEqual((report.players, report.clubs), (6, 1))
        self.assertEqual(report.unknown_fields, {"favourite_court": 1})

    def test_case_and_whitespace_duplicates_block(self):
        report = mig.precheck([player(email="pat@example.com"), player(email=" PAT@example.com")])
        self.assertFalse(report.ok)
        self.assertIn("duplicate email pat@example.com", report.blocking[0])

    def test_bad_values_block_rather_than_get_fixed(self):
        for overrides in ({"password": None}, {"firstName": "  "}, {"zip_code": "1234"},
                          {"dupr_rating": 9.0}, {"age": 7}, {"paddles": [{"brand": "A"}] * 4},
                          {"email": None}):
            with self.subTest(overrides=overrides):
                self.assertFalse(mig.precheck([player(**overrides)]).ok)

    def test_club_values_on_a_player_are_recorded_before_removal(self):
        report = mig.precheck([player(clubName="Old Club", phone="555")])
        self.assertTrue(report.ok)
        self.assertEqual(report.club_field_values[0]["clubName"], "Old Club")
        self.assertEqual(report.club_field_values[0]["phone"], "555")

    def test_player_sharing_an_email_with_a_club_is_a_warning(self):
        report = mig.precheck([player(email="dual@example.com"), club(email="dual@example.com")])
        self.assertTrue(report.ok)
        self.assertTrue(any("dual@example.com" in w for w in report.warnings))

    def test_clubs_are_not_validated_as_players(self):
        self.assertTrue(mig.precheck([club(zip_code="bad", dupr_rating=0.0)]).ok)


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.backup = realistic_population()
        self.migrated = [mig.migrated_view(d, NOW) for d in self.backup if not mig.is_club(d)]

    def test_a_correct_migration_has_no_problems(self):
        self.assertEqual(mig.verify(self.backup, self.migrated), [])

    def test_detects_a_lost_player(self):
        problems = mig.verify(self.backup, self.migrated[1:])
        self.assertTrue(any("missing after migration" in p for p in problems))

    def test_detects_a_changed_profile_field(self):
        self.migrated[0]["dupr_rating"] = 9.9
        self.assertTrue(any("dupr_rating changed" in p for p in mig.verify(self.backup, self.migrated)))

    def test_detects_a_wrong_password_hash(self):
        self.migrated[0]["password_hash"] = "other"
        self.assertTrue(any("password hash" in p for p in mig.verify(self.backup, self.migrated)))

    def test_detects_leftover_fields_and_surviving_clubs(self):
        self.migrated[0]["leagues"] = []
        survivors = self.migrated + [club()]
        problems = mig.verify(self.backup, survivors)
        self.assertTrue(any("leagues still present" in p for p in problems))
        self.assertTrue(any("not in the backup as a player" in p for p in problems))

    def test_detects_a_dropped_unknown_field(self):
        sam = next(d for d in self.migrated if d["email"] == "sam@example.com")
        del sam["favourite_court"]
        self.assertTrue(any("favourite_court" in p for p in mig.verify(self.backup, self.migrated)))


class TestApplyAndRollback(unittest.TestCase):
    def setUp(self):
        self.original = realistic_population()
        self.db = FakeDB(self.original)
        self.quiet = lambda *a, **k: None

    def test_apply_migrates_players_and_removes_clubs(self):
        mig.apply(self.db, "players_backup_test", NOW, log=self.quiet)

        players = self.db["players"].find()
        self.assertEqual(len(players), 6)
        self.assertFalse(any(mig.is_club(p) for p in players))
        self.assertTrue(all(p["schema_version"] == 2 for p in players))
        self.assertEqual(mig.verify(self.original, players), [])
        # The backup is the untouched original, clubs included.
        self.assertEqual(self.db["players_backup_test"].find(), self.original)
        # Every player with a rating got exactly one migrated history row.
        rated = [p for p in self.original if not mig.is_club(p) and p.get("dupr_rating") is not None]
        self.assertEqual(self.db["rating_history"].count_documents({"source": "migrated"}), len(rated))
        self.assertIn("email_unique", self.db.indexes["players"])
        levels = [kw.get("validationLevel") for _, kw in self.db.commands]
        self.assertEqual(levels, ["moderate", "strict"])

    def test_rerunning_is_a_no_op(self):
        mig.apply(self.db, "players_backup_1", NOW, log=self.quiet)
        after_first = self.db["players"].find()
        mig.apply(self.db, "players_backup_2", NOW + timedelta(hours=1), log=self.quiet)
        self.assertEqual(self.db["players"].find(), after_first)
        self.assertEqual(self.db["rating_history"].count_documents({"source": "migrated"}), 5)

    def test_blocking_precheck_stops_before_any_write(self):
        db = FakeDB([player(email="a@example.com"), player(email="A@example.com")])
        with self.assertRaises(mig.MigrationError):
            mig.apply(db, "players_backup_test", NOW, log=self.quiet)
        self.assertEqual(db.writes, 0)
        self.assertNotIn("players_backup_test", db.list_collection_names())

    def test_refuses_to_overwrite_an_existing_backup(self):
        self.db.data["players_backup_test"] = []
        with self.assertRaises(mig.MigrationError):
            mig.apply(self.db, "players_backup_test", NOW, log=self.quiet)
        self.assertEqual(self.db["players"].find(), self.original)

    def test_failed_post_check_keeps_the_backup_and_says_how_to_roll_back(self):
        with patch.object(mig, "verify", return_value=["simulated mismatch"]):
            with self.assertRaises(mig.MigrationError) as ctx:
                mig.apply(self.db, "players_backup_test", NOW, log=self.quiet)
        self.assertIn("--rollback --backup players_backup_test", str(ctx.exception))
        self.assertIn("players_backup_test", self.db.list_collection_names())
        # Never switched to strict after a failed check.
        self.assertNotIn("strict", [kw.get("validationLevel") for _, kw in self.db.commands])

    def test_rollback_restores_the_original_collection(self):
        mig.apply(self.db, "players_backup_test", NOW, log=self.quiet)
        mig.rollback(self.db, "players_backup_test", log=self.quiet)
        self.assertEqual(self.db["players"].find(), self.original)
        self.assertNotIn("players_backup_test", self.db.list_collection_names())
        self.assertEqual(self.db["rating_history"].count_documents({"source": "migrated"}), 0)

    def test_rollback_needs_an_existing_backup(self):
        with self.assertRaises(mig.MigrationError):
            mig.rollback(self.db, "players_backup_nope", log=self.quiet)


class TestCli(unittest.TestCase):
    def _run(self, db, argv):
        out = io.StringIO()
        with patch.object(mig, "get_client", return_value={"pickleball": db}), redirect_stdout(out):
            code = mig.main(argv)
        return code, out.getvalue()

    def test_default_run_is_read_only(self):
        db = FakeDB(realistic_population())
        code, out = self._run(db, [])
        self.assertEqual(code, 0)
        self.assertEqual(db.writes, 0)
        self.assertIn("DRY RUN - nothing was written", out)
        self.assertIn("6 player document(s) would be updated", out)
        self.assertNotIn("$2b$", out)  # password hashes are never printed

    def test_dry_run_exits_non_zero_on_blocking_problems(self):
        db = FakeDB([player(zip_code="12")])
        code, out = self._run(db, [])
        self.assertEqual(code, 1)
        self.assertIn("BLOCKING", out)

    def test_apply_requires_the_dump_confirmation(self):
        db = FakeDB(realistic_population())
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), \
                patch("sys.stderr", new_callable=io.StringIO):
            self._run(db, ["--apply"])
        self.assertEqual(db.writes, 0)


if __name__ == "__main__":
    unittest.main()
