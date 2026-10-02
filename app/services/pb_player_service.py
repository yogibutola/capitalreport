import bcrypt
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.services.pb_session import issue_session, session_claims
from app.store.mongo.pb_player_store import PBPlayerStore
from app.store.mongo.schema.players import SCHEMA_VERSION
from app.vo.pb.player import (
    PlayerSignup,
    PlayerResponse,
    PlayerLogin,
    ClubSignup,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    PlayerSearchResult,
    PlayerSearchResponse,
    MAX_PADDLES,
)
from app.utils.geo import (
    InvalidZipError,
    coordinates_for_zip,
    distance_miles,
    normalize_zip,
    zip_is_known,
)

logger = logging.getLogger(__name__)

RESET_TOKEN_EXPIRE_MINUTES = 30

# Fixed accounts created by seed_demo.py. The "Demo" buttons on the home page
# sign visitors straight into these; demo tokens carry a "demo" claim and are
# rejected by app.api.v1.deps for any non-GET request.
DEMO_ACCOUNTS = {
    "admin": "demo.club@stackedpaddle.com",
    "player": "demo.player@stackedpaddle.com",
}


class PBPlayerService:
    """Service for managing player operations"""
    
    def __init__(self, pb_player_store: PBPlayerStore, club_store=None):
        self.pb_player_store = pb_player_store
        self._club_store = club_store

    @property
    def club_store(self):
        """Clubs live in their own collection; created on first use so callers that
        only need player data don't have to supply one."""
        if self._club_store is None:
            from app.store.mongo.pb_club_store import PBClubStore
            self._club_store = PBClubStore()
        return self._club_store

    def _club_of(self, player: dict) -> dict | None:
        """The club this account runs, if any."""
        return self.club_store.get_club_by_owner(player["_id"]) if player.get("_id") else None

    @staticmethod
    def _password_hash(player: dict) -> str:
        # Migrated documents store ``password_hash``; documents written before the
        # v2 migration still have ``password``. Read both until the migration runs.
        return player.get("password_hash") or player.get("password") or ""

    @staticmethod
    def _new_player_doc(*, first_name: str, last_name: str, email: str, password_hash: str,
                        dupr_rating: float | None, state: str | None = None, city: str | None = None,
                        zip_code: str | None = None) -> dict:
        """A ``players`` document in the v2 shape (app/store/mongo/schema/players.py)."""
        now = datetime.now(timezone.utc)
        return {
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "firstName": first_name.strip(),
            "lastName": last_name.strip(),
            "dupr_rating": dupr_rating,
            "age": None,
            "state": state,
            "city": city,
            "zip_code": zip_code,
            "paddles": [],
            "is_demo": False,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            "schema_version": SCHEMA_VERSION,
        }

    def _session_response(self, player: dict, club: dict | None, demo: bool = False) -> PlayerResponse:
        """The signed-in response for ``player``: profile basics plus a fresh token."""
        token, claims = issue_session(player, club, demo=demo)
        return PlayerResponse(
            id=str(player.get('_id')),
            firstName=player['firstName'],
            lastName=player['lastName'],
            email=player['email'],
            dupr_rating=player.get('dupr_rating'),
            role=claims["role"],
            token=token,
            clubName=club["name"] if club else None,
            leagues=player.get('leagues', []),
            is_demo=demo,
        )

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt (truncates to 72 bytes due to bcrypt limitation)"""
        # bcrypt has a maximum password length of 72 bytes
        password_bytes = password.encode('utf-8')[:72]
        # Generate a salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        password_bytes = plain_password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))

    def signin_player(self, login_data: PlayerLogin) -> PlayerResponse:
        """
        Authenticate a player
        
        Args:
            login_data: PlayerLogin model with email and password
            
        Returns:
            PlayerResponse: Authenticated player data
            
        Raises:
            HTTPException: If authentication fails (401 Unauthorized)
        """
        # Find player by email
        player_data = self.pb_player_store.find_player_by_email(login_data.email)
        
        # Verify player exists and password matches
        if not player_data or not self.verify_password(login_data.password, self._password_hash(player_data)):
            self._audit_signin(login_data.email, None, 401, "Failed sign-in")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # The role is derived, never stored: superadmin from SUPERADMIN_EMAILS,
        # admin when the account runs a club, otherwise player (pb_session.py).
        response = self._session_response(player_data, self._club_of(player_data))
        self._audit_signin(player_data['email'], response.role, 200, "Signed in")
        return response

    @staticmethod
    def _audit_signin(email: str, role: str | None, status_code: int, action: str) -> None:
        """Record a sign-in attempt in the audit log (best-effort, never raises).

        The audit middleware can't see the attempted email (the request carries no
        token), so sign-ins are logged explicitly here - with the real actor - for
        the platform activity feed. The middleware skips /api/v1/signin to match.
        """
        try:
            from app.store.mongo.pb_audit_store import PBAuditStore
            from datetime import datetime, timezone
            PBAuditStore().record({
                "ts": datetime.now(timezone.utc),
                "actor": (email or "anonymous").lower(),
                "actor_role": role,
                "method": "POST",
                "path": "/api/v1/signin",
                "route": "/api/v1/signin",
                "status_code": status_code,
                "duration_ms": 0,
                "action": action,
                "client_ip": None,
                "error": None if status_code < 400 else "Invalid email or password",
            })
        except Exception:  # pragma: no cover - audit must never break sign-in
            logger.debug("Could not record sign-in audit entry", exc_info=True)


    def demo_signin(self, persona: str) -> PlayerResponse:
        """
        Sign in to a pre-seeded, read-only demo account (no password).

        Args:
            persona: "admin" or "player" - selects which demo account to enter.

        Returns:
            PlayerResponse: demo account data with a token that carries a
            "demo" claim (write requests using it are rejected with 403).

        Raises:
            HTTPException 404: If this environment has not been seeded (run seed_demo.py).
        """
        email = DEMO_ACCOUNTS.get(persona)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown demo persona",
            )

        player_data = self.pb_player_store.find_player_by_email(email)
        if not player_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The demo is not available right now. Please try again later.",
            )

        return self._session_response(player_data, self._club_of(player_data), demo=True)

    def change_password(self, email: str, req: ChangePasswordRequest) -> None:
        """
        Change an authenticated user's password.

        Raises:
            HTTPException 404: If the user no longer exists
            HTTPException 400: If the current password is wrong or unchanged
        """
        player = self.pb_player_store.find_player_by_email(email)
        if not player:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not self.verify_password(req.current_password, self._password_hash(player)):
            # 400 (not 401) on purpose - a 401 makes the frontend auth interceptor
            # force a logout mid-form. 400 maps to parseHttpError kind 'validation'.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        if req.current_password == req.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from the current password"
            )

        self.pb_player_store.update_player_password(email, self.hash_password(req.new_password))

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def forgot_password(self, req: ForgotPasswordRequest) -> None:
        """
        Issue a password-reset token for the given email, if it belongs to an account.

        Silently no-ops for unknown emails - the router always returns the same
        generic response so this endpoint can't be used to enumerate accounts.
        """
        player = self.pb_player_store.find_player_by_email(req.email)
        if not player:
            return

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        self.pb_player_store.set_reset_token(player['email'], self._hash_token(token), expires_at)

        # No email is sent yet. The link is a bearer credential for the account, so
        # it is only logged when a developer opts in locally - never in deployed
        # logs, where anyone with log access could use it.
        if os.getenv('LOG_PASSWORD_RESET_LINKS', '').lower() == 'true':
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:4200')
            reset_link = f"{frontend_url}/reset-password?token={token}"
            logger.info(f"[STUB EMAIL] Password reset link for {player['email']}: {reset_link}")
        else:
            logger.info(f"[STUB EMAIL] Password reset requested for {player['email']} (link not logged)")

    def reset_password(self, req: ResetPasswordRequest) -> None:
        """
        Set a new password using a token issued by forgot_password.

        Raises:
            HTTPException 400: If the token is unknown, already used, or expired
        """
        player = self.pb_player_store.find_player_by_reset_token_hash(self._hash_token(req.token))
        if not player or player.get('reset_token_expires', datetime.min) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        self.pb_player_store.reset_password(player['email'], self.hash_password(req.new_password))

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        """Trim an optional free-text field, collapsing blank input to None."""
        if value is None:
            return None
        return str(value).strip() or None

    @staticmethod
    def _normalize_paddles(raw: list | None) -> list[dict]:
        """Tidy a submitted paddle bag into what we're willing to store.

        Trims both halves, drops entries with no brand (a model on its own can't
        be rendered as a chip), collapses case-insensitive duplicates keeping the
        first spelling the player used, and caps the count. Returns plain dicts so
        ``$set`` writes clean BSON rather than Pydantic objects.
        """
        if not raw:
            return []

        cleaned: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for entry in raw:
            # Entries arrive as Paddle models from the VO, but tolerate dicts so
            # the method is usable from tests and any future caller.
            if isinstance(entry, dict):
                brand, model = entry.get("brand"), entry.get("model")
            else:
                brand, model = entry.brand, entry.model

            brand = str(brand).strip() if brand is not None else ""
            if not brand:
                continue
            model = str(model).strip() or None if model is not None else None

            key = (brand.casefold(), (model or "").casefold())
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({"brand": brand, "model": model})

        # The VO's max_length already 422s an oversized list; this is belt and braces.
        return cleaned[:MAX_PADDLES]

    @staticmethod
    def _reject_unknown_zip(zip_code: str | None) -> None:
        """422 when a ZIP is well-formed but isn't a real US ZIP.

        Raised as a Pydantic-shaped ``detail`` list so the frontend pins the
        message to the ZIP field rather than showing it as a form-level error.
        Blank input is fine — location is optional everywhere.
        """
        if zip_code and not zip_is_known(zip_code):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", "zip_code"],
                    "msg": "We don't recognise that ZIP code.",
                }],
            )

    def _to_profile_response(self, player: dict, club: dict | None, token: str | None = None) -> ProfileResponse:
        return ProfileResponse(
            id=str(player.get('_id')),
            firstName=player.get('firstName', ''),
            lastName=player.get('lastName', ''),
            email=player['email'],
            age=player.get('age'),
            dupr_rating=player.get('dupr_rating'),
            state=player.get('state'),
            city=player.get('city'),
            zip_code=player.get('zip_code'),
            # `or []` rather than a .get default: it also covers a stored null.
            paddles=player.get('paddles') or [],
            # A club owner's profile page edits their club too (clubs collection).
            clubName=club["name"] if club else None,
            address=club.get("address") if club else None,
            phone=club.get("phone") if club else None,
            role=session_claims(player, club)["role"],
            token=token,
        )

    def get_profile(self, email: str) -> ProfileResponse:
        """Return the authenticated user's profile."""
        player = self.pb_player_store.find_player_by_email(email)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._to_profile_response(player, self._club_of(player))

    def update_profile(self, email: str, req: ProfileUpdateRequest) -> ProfileResponse:
        """
        Apply a partial update to the authenticated user's profile.

        Player fields update the account. ``clubName``/``address``/``phone`` update
        the club the account runs, and are ignored for accounts without one.

        Raises:
            HTTPException 404: If the user no longer exists
            HTTPException 400: If a required name field is blanked out
            HTTPException 409: If the new email is already taken by someone else
        """
        player = self.pb_player_store.find_player_by_email(email)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        club = self._club_of(player)
        updates = req.model_dump(exclude_unset=True)
        club_updates = {key: updates.pop(key) for key in ("clubName", "address", "phone") if key in updates}

        if club and club_updates:
            if "clubName" in club_updates:
                if club_updates["clubName"] is None or not str(club_updates["clubName"]).strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Club name cannot be empty",
                    )
                club_updates["name"] = str(club_updates.pop("clubName")).strip()
            for key in ("address", "phone"):
                if key in club_updates and club_updates[key] is not None:
                    club_updates[key] = str(club_updates[key]).strip() or None

        for key in ("firstName", "lastName"):
            if key in updates:
                if updates[key] is None or not str(updates[key]).strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="First and last name cannot be empty",
                    )
                updates[key] = str(updates[key]).strip()

        for key in ("state", "city"):
            if key in updates and updates[key] is not None:
                updates[key] = str(updates[key]).strip() or None

        # Presence-tested, not truthiness-tested: an empty list is how the
        # profile form says "I've emptied my paddle bag", and it has to reach
        # the $set. Omitting the key entirely is what leaves paddles alone.
        if "paddles" in updates:
            updates["paddles"] = self._normalize_paddles(updates["paddles"])

        # The VO already normalized this to 5 digits or None; all that's left is
        # to check it's a ZIP that actually exists, so distance search can place
        # this player instead of silently skipping them.
        self._reject_unknown_zip(updates.get("zip_code"))

        # dupr_rating is not clearable from the profile form; drop an explicit null.
        if "dupr_rating" in updates and updates["dupr_rating"] is None:
            updates.pop("dupr_rating")

        new_email = updates.get("email")
        email_changed = bool(new_email) and new_email.lower() != email.lower()
        if email_changed:
            if self.pb_player_store.find_player_by_email(new_email):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email {new_email} is already in use",
                )
            updates["email"] = new_email.lower()
        else:
            updates.pop("email", None)

        try:
            updated = self.pb_player_store.update_player_profile(email, updates)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email {new_email} is already in use",
            )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if "dupr_rating" in updates and updates["dupr_rating"] != player.get("dupr_rating"):
            self.pb_player_store.record_rating(player["_id"], updates["dupr_rating"], "self")
        if club and club_updates:
            club = self.club_store.update_club(club["_id"], club_updates) or club

        # The JWT 'sub' is the email, so a change invalidates the current token.
        new_token = issue_session(updated, club)[0] if email_changed else None
        return self._to_profile_response(updated, club, token=new_token)

    def register_club(self, club_signup: "ClubSignup") -> PlayerResponse:
        """
        Sign up a club organiser: a normal account for the person, plus the club
        they run (a separate ``clubs`` record they own).

        Raises:
            HTTPException 409: If the email already has an account - an existing
            player creates a club from their account instead (POST /clubs).
        """
        from app.services.pb_club_service import PBClubService
        from app.vo.pb.club import ClubCreate

        owner = self._create_account(
            first_name=club_signup.firstName, last_name=club_signup.lastName,
            email=club_signup.email, password=club_signup.password, dupr_rating=None,
        )
        club = PBClubService(self.club_store, self.pb_player_store).create_club_with_owner(
            owner, ClubCreate(name=club_signup.clubName, address=club_signup.address, phone=club_signup.phone),
        )
        # The client navigates straight to /admin, which is auth-guarded, so the
        # response has to carry a token with the admin role.
        return self._session_response(owner, club)

    def register_player(self, player_signup: PlayerSignup) -> PlayerResponse:
        """
        Register a new player

        Args:
            player_signup: PlayerSignup model with registration data

        Returns:
            PlayerResponse model without password

        Raises:
            HTTPException: If email already exists (409 Conflict)
        """
        # Location is optional at signup, but if a ZIP was given it has to be a
        # real one - otherwise the account is invisible to distance search with
        # no feedback to the player.
        self._reject_unknown_zip(player_signup.zip_code)

        created_player = self._create_account(
            first_name=player_signup.firstName, last_name=player_signup.lastName,
            email=player_signup.email, password=player_signup.password,
            dupr_rating=player_signup.dupr_rating,
            state=self._clean_optional(player_signup.state),
            city=self._clean_optional(player_signup.city),
            zip_code=player_signup.zip_code,  # Already normalized to 5 digits by the VO
        )

        # Signing up signs you in: the client navigates straight to the dashboard,
        # so without a token here the first authenticated request 401s and the
        # interceptor bounces the brand-new account back to the login screen.
        return self._session_response(created_player, None)

    def _create_account(self, *, first_name: str, last_name: str, email: str, password: str,
                        dupr_rating: float | None, state: str | None = None, city: str | None = None,
                        zip_code: str | None = None) -> dict:
        """Insert a new account (v2 shape) and seed its rating history. 409 if the email is taken."""
        if self.pb_player_store.find_player_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email {email} already exists"
            )
        doc = self._new_player_doc(
            first_name=first_name, last_name=last_name, email=email,
            password_hash=self.hash_password(password), dupr_rating=dupr_rating,
            state=state, city=city, zip_code=zip_code,
        )
        try:
            created = self.pb_player_store.create_player(doc)
        except DuplicateKeyError:
            # Two signups with the same email raced past the check above; the
            # unique email index (players v2) let only one through.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email {email} already exists"
            )
        if dupr_rating is not None:
            self.pb_player_store.record_rating(created["_id"], dupr_rating, "self")
        return created

    def get_all_players(self) -> list[PlayerResponse]:
        """Get all players from the database"""
        players_data = self.pb_player_store.get_all_players()
        return [
            PlayerResponse(
                id=player.get('_id'),
                firstName=player['firstName'],
                lastName=player['lastName'],
                email=player['email'],
                # .get, not [] - a seeded or legacy doc without a rating used to
                # 500 this whole listing.
                dupr_rating=player.get('dupr_rating'),
                role=player.get('role', 'player'),
                leagues=player.get('leagues', [])
            ) for player in players_data
        ]

    def search_players(self, searcher_email: str, first_name: str = None, last_name: str = None,
                       dupr_min: float = None, dupr_max: float = None,
                       radius_miles: float = None, origin_zip: str = None,
                       limit: int = 200) -> PlayerSearchResponse:
        """Find other players by name, DUPR band and/or distance.

        Name and rating filters run in Mongo; distance runs here, because the
        player documents hold a ZIP rather than coordinates. A player whose ZIP
        can't be placed is dropped when a radius is in play — the same rule that
        drops an unrated player when a DUPR band is set.

        ``origin_zip`` lets the searcher measure from somewhere other than home
        (a club across town, a trip). It falls back to their profile ZIP.

        Raises:
            HTTPException 400: inverted DUPR range, or a radius with no usable origin
            HTTPException 404: the searcher's own account no longer exists
        """
        if dupr_min is not None and dupr_max is not None and dupr_max < dupr_min:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "dupr_range_inverted",
                    "message": "Max rating must be at least the min rating.",
                },
            )

        # Resolve the origin once, before the scan.
        origin = None
        resolved_zip = None
        if radius_miles is not None:
            if origin_zip:
                try:
                    resolved_zip = normalize_zip(origin_zip)
                except InvalidZipError:
                    resolved_zip = None
                origin = coordinates_for_zip(resolved_zip)
                if origin is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "origin_zip_unknown",
                            "message": "We don't recognise that ZIP code.",
                        },
                    )
            else:
                searcher = self.pb_player_store.find_player_by_email(searcher_email)
                if not searcher:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
                resolved_zip = searcher.get('zip_code')
                origin = coordinates_for_zip(resolved_zip)
                if origin is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "origin_zip_missing",
                            "message": "Enter a ZIP code, or add one to your profile, "
                                       "to search by distance.",
                        },
                    )

        docs = self.pb_player_store.find_players(
            first_name=first_name,
            last_name=last_name,
            dupr_min=dupr_min,
            dupr_max=dupr_max,
            exclude_email=searcher_email,
        )

        results: list[PlayerSearchResult] = []
        for doc in docs:
            miles = None
            if origin is not None:
                coords = coordinates_for_zip(doc.get('zip_code'))
                if coords is None:
                    continue  # Can't place them, so we can't honour the radius.
                miles = distance_miles(origin, coords)
                if miles > radius_miles:
                    continue
                miles = round(miles, 1)

            results.append(PlayerSearchResult(
                id=str(doc.get('_id')),
                firstName=doc.get('firstName', ''),
                lastName=doc.get('lastName', ''),
                email=doc['email'],
                dupr_rating=doc.get('dupr_rating'),
                role=doc.get('role', 'player'),
                city=doc.get('city'),
                state=doc.get('state'),
                paddles=doc.get('paddles') or [],
                distance_miles=miles,
            ))

        if origin is not None:
            results.sort(key=lambda r: r.distance_miles)
        else:
            results.sort(key=lambda r: (r.lastName.lower(), r.firstName.lower()))

        results = results[:limit]
        return PlayerSearchResponse(
            results=results,
            count=len(results),  # Rows returned, not a total - the limit applies first.
            origin_zip=resolved_zip,
            radius_miles=radius_miles,
        )

    def get_player_details(self):
        return "Player details"

    def get_player_stats(self):
        return "Player stats"

    def update_player_league(self, email: str, league_id: str, league_name: str):
        """Update or add a league for a player"""
        return self.pb_player_store.update_player_league_details(email, league_id, league_name)

    def get_league_by_player_email(self, email_id: str):
        return self.pb_player_store.get_league_by_player_email(email_id)
        