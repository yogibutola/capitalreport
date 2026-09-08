"""One-off cleanup: remove club (admin) accounts that were registered as players.

Club accounts share the ``players`` collection with real players, tagged
``role="admin"``. They are not players, but nothing used to stop them being
registered into a league / tournament / group, so some rosters contain them.
This script pulls those admin emails back out of the roster arrays.

It does NOT delete any account and does NOT touch match documents.

Usage:
    export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
    python cleanup_admin_roster_entries.py            # dry run - report only
    python cleanup_admin_roster_entries.py --apply    # perform the writes

Run once per environment after deploying the get_all_players() filter.
"""
import argparse
import os
import sys

from pymongo import MongoClient
from pymongo.server_api import ServerApi

DB_NAME = "pickleball"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Perform the writes (default: dry run)")
    args = parser.parse_args()

    uri = os.getenv("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI environment variable must be set")

    client = MongoClient(uri, server_api=ServerApi("1"))
    db = client[DB_NAME]

    admin_emails = sorted(
        doc["email"].lower()
        for doc in db["players"].find({"role": "admin"}, {"email": 1})
        if doc.get("email")
    )
    if not admin_emails:
        print("No admin accounts found - nothing to do.")
        return

    print(f"Found {len(admin_emails)} admin account(s):")
    for e in admin_emails:
        print(f"  - {e}")
    print(f"\n{'APPLYING CHANGES' if args.apply else 'DRY RUN - no writes'}\n")

    admin_set = set(admin_emails)
    total = 0

    # --- league.players[] (array of {firstName, lastName, email, dupr_rating}) ---
    for lg in db["league"].find({"players.email": {"$in": admin_emails}}):
        hits = [p.get("email") for p in lg.get("players", []) if (p.get("email") or "").lower() in admin_set]
        name = lg.get("league_name", lg["_id"])
        print(f"league   '{name}': remove {hits}")
        total += len(hits)
        if args.apply:
            db["league"].update_one(
                {"_id": lg["_id"]},
                {"$pull": {"players": {"email": {"$in": list(hits)}}}},
            )

    # --- tournament.players[] (array of Player) + flag admin teams ---
    for t in db["tournament"].find(
        {"$or": [
            {"players.email": {"$in": admin_emails}},
            {"teams.participant_one_email": {"$in": admin_emails}},
            {"teams.participant_two_email": {"$in": admin_emails}},
        ]}
    ):
        name = t.get("tournament_name", t["_id"])
        hits = [p.get("email") for p in t.get("players", []) if (p.get("email") or "").lower() in admin_set]
        if hits:
            print(f"tournament '{name}': remove players {hits}")
            total += len(hits)
            if args.apply:
                db["tournament"].update_one(
                    {"_id": t["_id"]},
                    {"$pull": {"players": {"email": {"$in": list(hits)}}}},
                )
        for team in t.get("teams", []):
            tp = [team.get("participant_one_email"), team.get("participant_two_email")]
            if any((x or "").lower() in admin_set for x in tp):
                print(f"tournament '{name}': ⚠️  team {team.get('team_id', tp)} has an admin participant "
                      f"- remove/redraw this team manually")

    # --- groups.members[] (array of email strings) ---
    for g in db["groups"].find({"members": {"$in": admin_emails}}):
        hits = [m for m in g.get("members", []) if (m or "").lower() in admin_set]
        name = g.get("group_name", g["_id"])
        print(f"group    '{name}': remove {hits}")
        total += len(hits)
        if args.apply:
            db["groups"].update_one({"_id": g["_id"]}, {"$pull": {"members": {"$in": list(hits)}}})

    # --- the admin's own players.leagues[] entries ---
    for doc in db["players"].find({"role": "admin", "leagues": {"$exists": True, "$ne": []}}):
        n = len(doc.get("leagues", []))
        print(f"players  '{doc['email']}': clear {n} stray leagues[] entr{'y' if n == 1 else 'ies'}")
        total += n
        if args.apply:
            db["players"].update_one({"_id": doc["_id"]}, {"$set": {"leagues": []}})

    print(f"\n{'Removed' if args.apply else 'Would remove'} {total} roster entr{'y' if total == 1 else 'ies'}.")
    if not args.apply and total:
        print("Re-run with --apply to perform the writes.")


if __name__ == "__main__":
    main()
