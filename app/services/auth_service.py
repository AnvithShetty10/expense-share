"""Authentication logic"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ConflictError, AuthenticationError
from app.config import get_settings

settings = get_settings()


class AuthService:
    """Service for authentication operations"""

    @staticmethod
    async def register_user(user_data: UserCreate, db: AsyncSession) -> User:
        """
        Register a new user.

        Args:
            user_data: User registration data
            db: Database session

        Returns:
            Created user

        Raises:
            ConflictError: If email or username already exists
        """
        # Check if email already exists
        if await UserRepository.check_email_exists(db, user_data.email):
            raise ConflictError(f"Email '{user_data.email}' is already registered")

        # Check if username already exists
        if await UserRepository.check_username_exists(db, user_data.username):
            raise ConflictError(f"Username '{user_data.username}' is already taken")

        # Create new user with hashed password
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            full_name=user_data.full_name,
            is_active=True
        )

        # Save to database
        created_user = await UserRepository.create(db, new_user)
        await db.commit()

        return created_user

    @staticmethod
    async def authenticate_user(identifier: str, password: str, db: AsyncSession) -> Optional[User]:
        """
        Authenticate user with email/username and password.

        Args:
            identifier: Email or username
            password: Plain text password
            db: Database session

        Returns:
            User if authentication successful, None otherwise
        """
        # Get user by email or username
        user = await UserRepository.get_by_email_or_username(db, identifier)

        if not user:
            return None

        # Verify password
        if not verify_password(password, user.hashed_password):
            return None

        # Check if user is active
        if not user.is_active:
            return None

        return user

    @staticmethod
    def create_access_token_for_user(user: User) -> dict:
        """
        Create JWT access token for user.

        Args:
            user: User object

        Returns:
            Dictionary with access_token, token_type, and expires_in
        """
        token_data = {"sub": str(user.id)}
        access_token = create_access_token(token_data)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60  # Convert to seconds
        }

    @staticmethod
    async def login(identifier: str, password: str, db: AsyncSession) -> dict:
        """
        Login user and return access token.

        Args:
            identifier: Email or username
            password: Plain text password
            db: Database session

        Returns:
            Token response with access_token, token_type, and expires_in

        Raises:
            AuthenticationError: If credentials are invalid
        """
        user = await AuthService.authenticate_user(identifier, password, db)

        if not user:
            raise AuthenticationError("Incorrect email/username or password")

        return AuthService.create_access_token_for_user(user)
