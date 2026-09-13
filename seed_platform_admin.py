"""Seed an application-admin ("platform") account plus a little data for the
hidden console at /x9k2-console.

Creates (idempotently - safe to re-run):

  * a normal account   platform.admin@test.com / Password@123
    It becomes a superadmin ONLY when the backend runs with
        SUPERADMIN_EMAILS=platform.admin@test.com
  * a club             pc.club@test.com / Password@123
  * two players         pc.player1@test.com, pc.player2@test.com / Password@123

so the console's Clubs and Players tables are never empty in a fresh test DB.

Usage:
    export MONGO_URI="mongodb://localhost:27017/?directConnection=true"
    python seed_platform_admin.py

Used by frontend/e2e/platform-console.spec.ts. Run once per environment.
"""
import sys

from fastapi import HTTPException

from app.services.pb_player_service import PBPlayerService
from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import ClubSignup, PlayerSignup

PASSWORD = "Password@123"
SUPERADMIN_EMAIL = "platform.admin@test.com"
CLUB_EMAIL = "pc.club@test.com"
PLAYER_EMAILS = ["pc.player1@test.com", "pc.player2@test.com"]


def _svc() -> PBPlayerService:
    return PBPlayerService(PBPlayerStore())


def _ensure_player(svc, first, last, email):
    try:
        svc.register_player(PlayerSignup(
            firstName=first, lastName=last, email=email,
            password=PASSWORD, dupr_rating=3.5,
        ))
        print(f"created player {email}")
    except HTTPException as e:
        if e.status_code == 409:
            print(f"player {email} already exists")
        else:
            raise


def main():
    svc = _svc()

    # The superadmin signs in as a normal account; SUPERADMIN_EMAILS elevates it.
    _ensure_player(svc, "Platform", "Admin", SUPERADMIN_EMAIL)

    try:
        svc.register_club(ClubSignup(
            clubName="Platform Console Test Club", email=CLUB_EMAIL, password=PASSWORD,
            address="1 Test Way", phone="555-0100",
        ))
        print(f"created club {CLUB_EMAIL}")
    except HTTPException as e:
        if e.status_code == 409:
            print(f"club {CLUB_EMAIL} already exists")
        else:
            raise

    for i, email in enumerate(PLAYER_EMAILS, start=1):
        _ensure_player(svc, "Console", f"Player{i}", email)

    print("\n==============================================")
    print("Platform console seed complete.")
    print(f"Superadmin login: {SUPERADMIN_EMAIL} / {PASSWORD}")
    print(f"Backend must run with SUPERADMIN_EMAILS={SUPERADMIN_EMAIL}")
    print("==============================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"seed failed: {e}")
        sys.exit(1)
