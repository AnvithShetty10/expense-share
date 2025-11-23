"""Auth endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserCreate, UserResponse
from app.schemas.auth import Token
from app.services.auth_service import AuthService
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import ConflictError, AuthenticationError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        Created user (without password)

    Raises:
        409: If email or username already exists
    """
    try:
        user = await AuthService.register_user(user_data, db)
        return UserResponse.model_validate(user)
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email/username and password.

    OAuth2 compatible token login, get an access token for future requests.

    Args:
        form_data: OAuth2 password request form (username and password)
        db: Database session

    Returns:
        Access token response

    Raises:
        401: If credentials are invalid
    """
    try:
        token_response = await AuthService.login(form_data.username, form_data.password, db)
        return Token(**token_response)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user profile (without password)
    """
    return UserResponse.model_validate(current_user)
