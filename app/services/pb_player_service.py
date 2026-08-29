import bcrypt
from fastapi import HTTPException, status

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import (
    PlayerSignup,
    Player,
    PlayerResponse,
    PlayerLogin,
    ClubSignup,
    ChangePasswordRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.utils.security import create_access_token


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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Generate access token
        access_token = create_access_token(
            data={"sub": player_data['email'], "role": player_data.get('role', 'player')}
        )
        
        # Return player profile with token
        return PlayerResponse(
            id=str(player_data.get('_id')),
            firstName=player_data['firstName'],
            lastName=player_data['lastName'],
            email=player_data['email'],
            dupr_rating=player_data['dupr_rating'],
            role=player_data.get('role', 'player'),
            token=access_token,
            leagues=player_data.get('leagues', [])
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
        player_only = {"firstName", "lastName", "age", "dupr_rating", "state", "city"}
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
            new_token = create_access_token(
                data={"sub": new_email.lower(), "role": player.get("role", "player")}
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

        # Return response
        return PlayerResponse(
            id=created_player.get('_id'),
            firstName=created_player['firstName'],
            lastName=created_player['lastName'],
            email=created_player['email'],
            dupr_rating=created_player['dupr_rating'],
            role=created_player.get('role', 'admin'),
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
            leagues=[]
        )
        
        # Store in database
        player_data = player.model_dump(exclude={'id'})  # Exclude None id
        created_player = self.pb_player_store.create_player(player_data)
        
        # Return response without password
        return PlayerResponse(
            id=created_player.get('_id'),
            firstName=created_player['firstName'],
            lastName=created_player['lastName'],
            email=created_player['email'],
            dupr_rating=created_player['dupr_rating'],
            role=created_player.get('role', 'player'),
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
                dupr_rating=player['dupr_rating'],
                role=player.get('role', 'player'),
                leagues=player.get('leagues', [])
            ) for player in players_data
        ]

    def get_player_details(self):
        return "Player details"

    def get_player_stats(self):
        return "Player stats"

    def update_player_league(self, email: str, league_id: str, league_name: str):
        """Update or add a league for a player"""
        return self.pb_player_store.update_player_league_details(email, league_id, league_name)

    def get_league_by_player_email(self, email_id: str):
        return self.pb_player_store.get_league_by_player_email(email_id)
        