import bcrypt
from fastapi import HTTPException, status

from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.player import PlayerSignup, Player, PlayerResponse, PlayerLogin, ClubSignup
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
        