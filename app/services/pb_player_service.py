import bcrypt
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import (
    PlayerSignup,
    Player,
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
from app.utils.security import create_access_token, is_superadmin_email

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
    
    def __init__(self, pb_player_store: PBPlayerStore):
        self.pb_player_store = pb_player_store

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
        if not player_data or not self.verify_password(login_data.password, player_data['password']):
            self._audit_signin(login_data.email, None, 401, "Failed sign-in")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Emails in the SUPERADMIN_EMAILS allowlist are elevated to the platform
        # ("superadmin") role for this session; the stored doc keeps its own role.
        role = player_data.get('role', 'player')
        if is_superadmin_email(player_data['email']):
            role = 'superadmin'

        self._audit_signin(player_data['email'], role, 200, "Signed in")

        # Generate access token
        access_token = create_access_token(
            data={"sub": player_data['email'], "role": role}
        )

        # Return player profile with token
        return PlayerResponse(
            id=str(player_data.get('_id')),
            firstName=player_data['firstName'],
            lastName=player_data['lastName'],
            email=player_data['email'],
            dupr_rating=player_data['dupr_rating'],
            role=role,
            token=access_token,
            leagues=player_data.get('leagues', [])
        )

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

        role = player_data.get('role', 'player')
        access_token = create_access_token(
            data={"sub": player_data['email'], "role": role, "demo": True}
        )

        return PlayerResponse(
            id=str(player_data.get('_id')),
            firstName=player_data['firstName'],
            lastName=player_data['lastName'],
            email=player_data['email'],
            dupr_rating=player_data.get('dupr_rating') or 0.0,
            role=role,
            token=access_token,
            clubName=player_data.get('clubName'),
            leagues=player_data.get('leagues', []),
            is_demo=True,
        )

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

        if not self.verify_password(req.current_password, player.get('password', '')):
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

        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:4200')
        reset_link = f"{frontend_url}/reset-password?token={token}"
        logger.info(f"[STUB EMAIL] Password reset link for {player['email']}: {reset_link}")

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

    @staticmethod
    def _to_profile_response(player: dict, token: str | None = None) -> ProfileResponse:
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
            clubName=player.get('clubName'),
            address=player.get('address'),
            phone=player.get('phone'),
            role=player.get('role', 'player'),
            token=token,
        )

    def get_profile(self, email: str) -> ProfileResponse:
        """Return the authenticated user's profile."""
        player = self.pb_player_store.find_player_by_email(email)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._to_profile_response(player)

    def update_profile(self, email: str, req: ProfileUpdateRequest) -> ProfileResponse:
        """
        Apply a partial update to the authenticated user's profile.

        Raises:
            HTTPException 404: If the user no longer exists
            HTTPException 400: If a required name field is blanked out
            HTTPException 409: If the new email is already taken by someone else
        """
        player = self.pb_player_store.find_player_by_email(email)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        is_club = player.get("role") == "admin"
        updates = req.model_dump(exclude_unset=True)

        # Keep only the fields that make sense for this account type.
        player_only = {"firstName", "lastName", "age", "dupr_rating", "state", "city", "zip_code",
                       "paddles"}
        club_only = {"clubName", "address", "phone"}
        for key in (club_only if not is_club else player_only):
            updates.pop(key, None)

        if is_club:
            if "clubName" in updates:
                if updates["clubName"] is None or not str(updates["clubName"]).strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Club name cannot be empty",
                    )
                updates["clubName"] = str(updates["clubName"]).strip()
                # The header greets the club by firstName; keep it in sync.
                updates["firstName"] = updates["clubName"]
            for key in ("address", "phone"):
                if key in updates and updates[key] is not None:
                    updates[key] = str(updates[key]).strip() or None
        else:
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

        new_token = None
        new_email = updates.get("email")
        if new_email and new_email.lower() != email.lower():
            if self.pb_player_store.find_player_by_email(new_email):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email {new_email} is already in use",
                )
            updates["email"] = new_email.lower()
            # The JWT 'sub' is the email, so a change invalidates the current token.
            token_role = player.get("role", "player")
            if is_superadmin_email(new_email):
                token_role = "superadmin"
            new_token = create_access_token(
                data={"sub": new_email.lower(), "role": token_role}
            )
        else:
            updates.pop("email", None)

        updated = self.pb_player_store.update_player_profile(email, updates)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._to_profile_response(updated, token=new_token)

    def register_club(self, club_signup: "ClubSignup") -> PlayerResponse:
        """
        Register a new club (admin)
        """
        # Check if email already exists
        existing_player = self.pb_player_store.find_player_by_email(club_signup.email)
        if existing_player:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email {club_signup.email} already exists"
            )

        # Hash the password
        hashed_password = self.hash_password(club_signup.password)

        # Create player model with admin role
        player = Player(
            firstName=club_signup.clubName,  # Store club name as first name for now
            lastName="Admin",
            email=club_signup.email.lower(),
            password=hashed_password,
            dupr_rating=0.0, # Not relevant for club admin
            role="admin",
            clubName=club_signup.clubName,
            address=club_signup.address,
            phone=club_signup.phone,
            leagues=[]
        )

        # Store in database
        player_data = player.model_dump(exclude={'id'})
        created_player = self.pb_player_store.create_player(player_data)

        # Same as register_player: the client navigates straight to /admin, which is
        # auth-guarded, so a missing token logs the brand-new club straight back out.
        role = created_player.get('role', 'admin')
        access_token = create_access_token(
            data={"sub": created_player['email'], "role": role}
        )

        # Return response
        return PlayerResponse(
            id=created_player.get('_id'),
            firstName=created_player['firstName'],
            lastName=created_player['lastName'],
            email=created_player['email'],
            dupr_rating=created_player['dupr_rating'],
            role=role,
            token=access_token,
            clubName=created_player.get('clubName'),
            leagues=created_player.get('leagues', [])
        )

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
        # Check if email already exists
        existing_player = self.pb_player_store.find_player_by_email(player_signup.email)
        if existing_player:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Player with email {player_signup.email} already exists"
            )
        
        # Location is optional at signup, but if a ZIP was given it has to be a
        # real one - otherwise the account is invisible to distance search with
        # no feedback to the player.
        self._reject_unknown_zip(player_signup.zip_code)

        # Hash the password
        hashed_password = self.hash_password(player_signup.password)

        # Create player model
        player = Player(
            firstName=player_signup.firstName,
            lastName=player_signup.lastName,
            email=player_signup.email.lower(),  # Store in lowercase
            password=hashed_password,
            dupr_rating=player_signup.dupr_rating,
            role="player",  # Default role
            state=self._clean_optional(player_signup.state),
            city=self._clean_optional(player_signup.city),
            zip_code=player_signup.zip_code,  # Already normalized to 5 digits by the VO
            leagues=[]
        )
        
        # Store in database
        player_data = player.model_dump(exclude={'id'})  # Exclude None id
        created_player = self.pb_player_store.create_player(player_data)
        
        # Signing up signs you in: the client navigates straight to the dashboard,
        # so without a token here the first authenticated request 401s and the
        # interceptor bounces the brand-new account back to the login screen.
        role = created_player.get('role', 'player')
        access_token = create_access_token(
            data={"sub": created_player['email'], "role": role}
        )

        # Return response without password
        return PlayerResponse(
            id=created_player.get('_id'),
            firstName=created_player['firstName'],
            lastName=created_player['lastName'],
            email=created_player['email'],
            dupr_rating=created_player['dupr_rating'],
            role=role,
            token=access_token,
            leagues=created_player.get('leagues', [])
        )

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
        