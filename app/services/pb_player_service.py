import bcrypt
from fastapi import HTTPException, status

from app.store.pb_mongo_db_store import PBMongoDBStore
from app.vo.pb.player import PlayerSignup, Player, PlayerResponse


class PBPlayerService:
    """Service for managing player operations"""
    
    def __init__(self, pb_mongo_db_store: PBMongoDBStore):
        self.pb_mongo_db_store = pb_mongo_db_store

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
        existing_player = self.pb_mongo_db_store.find_player_by_email(player_signup.email)
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
            dupr_rating=player_signup.dupr_rating
        )
        
        # Store in database
        player_data = player.model_dump(exclude={'id'})  # Exclude None id
        created_player = self.pb_mongo_db_store.create_player(player_data)
        
        # Return response without password
        return PlayerResponse(
            id=created_player.get('_id'),
            firstName=created_player['firstName'],
            lastName=created_player['lastName'],
            email=created_player['email'],
            dupr_rating=created_player['dupr_rating']
        )
