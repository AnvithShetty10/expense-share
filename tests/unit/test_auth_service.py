"""Unit tests for authentication service"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService


@pytest.fixture
def mock_db():
    """Create mock database session"""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def sample_user_data():
    """Sample user registration data"""
    return UserCreate(
        email="test@example.com",
        username="testuser",
        password="SecurePass123!",
        full_name="Test User",
    )


@pytest.fixture
def mock_user():
    """Create mock user object"""
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        hashed_password="$2b$12$hashedpassword",
        full_name="Test User",
        is_active=True,
    )
    return user


class TestRegisterUser:
    """Test user registration"""

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    @patch("app.services.auth_service.hash_password")
    @patch("app.services.user_service.UserService.invalidate_user_count_cache")
    async def test_register_user_success(
        self,
        mock_invalidate_cache,
        mock_hash_password,
        mock_user_repo,
        mock_db,
        sample_user_data,
        mock_user,
    ):
        """Test successful user registration"""
        # Setup mocks (must return awaitables)
        mock_user_repo.check_email_exists = AsyncMock(return_value=False)
        mock_user_repo.check_username_exists = AsyncMock(return_value=False)
        mock_hash_password.return_value = "$2b$12$hashedpassword"
        mock_user_repo.create = AsyncMock(return_value=mock_user)
        mock_invalidate_cache.return_value = True

        # Register user
        result = await AuthService.register_user(sample_user_data, mock_db)

        # Assertions
        assert result == mock_user
        mock_user_repo.check_email_exists.assert_called_once_with(
            mock_db, sample_user_data.email
        )
        mock_user_repo.check_username_exists.assert_called_once_with(
            mock_db, sample_user_data.username
        )
        mock_hash_password.assert_called_once_with(sample_user_data.password)
        mock_user_repo.create.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_invalidate_cache.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    async def test_register_user_duplicate_email(
        self, mock_user_repo, mock_db, sample_user_data
    ):
        """Test registration with duplicate email fails"""
        # Setup mock - email already exists (must return awaitable)
        mock_user_repo.check_email_exists = AsyncMock(return_value=True)

        # Attempt to register
        with pytest.raises(ConflictError, match="Email.*already registered"):
            await AuthService.register_user(sample_user_data, mock_db)

        # Should not check username or create user
        mock_user_repo.check_username_exists.assert_not_called()
        mock_user_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    async def test_register_user_duplicate_username(
        self, mock_user_repo, mock_db, sample_user_data
    ):
        """Test registration with duplicate username fails"""
        # Setup mocks - email OK, username exists (must return awaitables)
        mock_user_repo.check_email_exists = AsyncMock(return_value=False)
        mock_user_repo.check_username_exists = AsyncMock(return_value=True)

        # Attempt to register
        with pytest.raises(ConflictError, match="Username.*already taken"):
            await AuthService.register_user(sample_user_data, mock_db)

        # Should not create user
        mock_user_repo.create.assert_not_called()


class TestAuthenticateUser:
    """Test user authentication"""

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    @patch("app.services.auth_service.verify_password")
    async def test_authenticate_user_success(
        self, mock_verify_password, mock_user_repo, mock_db, mock_user
    ):
        """Test successful authentication"""
        # Setup mocks (must return awaitable)
        mock_user_repo.get_by_email_or_username = AsyncMock(return_value=mock_user)
        mock_verify_password.return_value = True

        # Authenticate
        result = await AuthService.authenticate_user("testuser", "password", mock_db)

        # Assertions
        assert result == mock_user
        mock_user_repo.get_by_email_or_username.assert_called_once_with(
            mock_db, "testuser"
        )
        mock_verify_password.assert_called_once_with(
            "password", mock_user.hashed_password
        )

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    async def test_authenticate_user_not_found(self, mock_user_repo, mock_db):
        """Test authentication with non-existent user"""
        # Setup mock - user not found (must return awaitable)
        mock_user_repo.get_by_email_or_username = AsyncMock(return_value=None)

        # Authenticate
        result = await AuthService.authenticate_user("nonexistent", "password", mock_db)

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    @patch("app.services.auth_service.verify_password")
    async def test_authenticate_user_wrong_password(
        self, mock_verify_password, mock_user_repo, mock_db, mock_user
    ):
        """Test authentication with wrong password"""
        # Setup mocks (must return awaitable)
        mock_user_repo.get_by_email_or_username = AsyncMock(return_value=mock_user)
        mock_verify_password.return_value = False  # Wrong password

        # Authenticate
        result = await AuthService.authenticate_user(
            "testuser", "wrongpassword", mock_db
        )

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.auth_service.UserRepository")
    @patch("app.services.auth_service.verify_password")
    async def test_authenticate_user_inactive(
        self, mock_verify_password, mock_user_repo, mock_db, mock_user
    ):
        """Test authentication with inactive user"""
        # Setup mocks (must return awaitable)
        mock_user.is_active = False  # User is inactive
        mock_user_repo.get_by_email_or_username = AsyncMock(return_value=mock_user)
        mock_verify_password.return_value = True

        # Authenticate
        result = await AuthService.authenticate_user("testuser", "password", mock_db)

        # Should return None for inactive user
        assert result is None


class TestCreateAccessToken:
    """Test access token creation"""

    @patch("app.services.auth_service.create_access_token")
    @patch("app.services.auth_service.get_settings")
    def test_create_access_token_for_user(
        self, mock_get_settings, mock_create_token, mock_user
    ):
        """Test creating access token for user"""
        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.access_token_expire_minutes = 30
        mock_get_settings.return_value = mock_settings
        mock_create_token.return_value = "mock_jwt_token"

        # Create token
        result = AuthService.create_access_token_for_user(mock_user)

        # Assertions
        assert result["access_token"] == "mock_jwt_token"
        assert result["token_type"] == "bearer"
        assert result["expires_in"] == 1800  # 30 minutes * 60 seconds

        # Verify create_access_token was called with correct data
        call_args = mock_create_token.call_args[0][0]
        assert call_args["sub"] == str(mock_user.id)


class TestLogin:
    """Test login functionality"""

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService.authenticate_user")
    @patch("app.services.auth_service.AuthService.create_access_token_for_user")
    async def test_login_success(
        self, mock_create_token, mock_authenticate, mock_db, mock_user
    ):
        """Test successful login"""
        # Setup mocks
        mock_authenticate.return_value = mock_user
        mock_token_response = {
            "access_token": "mock_token",
            "token_type": "bearer",
            "expires_in": 1800,
        }
        mock_create_token.return_value = mock_token_response

        # Login
        result = await AuthService.login("testuser", "password", mock_db)

        # Assertions
        assert result == mock_token_response
        mock_authenticate.assert_called_once_with("testuser", "password", mock_db)
        mock_create_token.assert_called_once_with(mock_user)

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService.authenticate_user")
    async def test_login_invalid_credentials(self, mock_authenticate, mock_db):
        """Test login with invalid credentials"""
        # Setup mock - authentication fails
        mock_authenticate.return_value = None

        # Attempt login
        with pytest.raises(
            AuthenticationError, match="Incorrect email/username or password"
        ):
            await AuthService.login("testuser", "wrongpassword", mock_db)

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService.authenticate_user")
    async def test_login_with_email(
        self, mock_authenticate, mock_db, mock_user
    ):
        """Test login with email instead of username"""
        # Setup mock
        mock_authenticate.return_value = mock_user

        # Mock token creation
        with patch.object(
            AuthService,
            "create_access_token_for_user",
            return_value={
                "access_token": "token",
                "token_type": "bearer",
                "expires_in": 1800,
            },
        ):
            result = await AuthService.login("test@example.com", "password", mock_db)

        # Should call authenticate with email
        mock_authenticate.assert_called_once_with("test@example.com", "password", mock_db)
        assert "access_token" in result
