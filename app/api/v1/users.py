"""User endpoints"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.user import PaginationMeta, UserListResponse, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        None, description="Search users by name, email, or username"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of users with pagination and search.

    Search filters users by username, email, or full name.
    Results are paginated and include metadata.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        search: Optional search term
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated list of users
    """
    users, total_count = await UserService.list_users(
        db, page=page, page_size=page_size, search=search, use_cache=True
    )

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    # Convert to response models
    user_responses = [UserResponse.model_validate(user) for user in users]

    pagination = PaginationMeta(
        page=page, page_size=page_size, total_items=total_count, total_pages=total_pages
    )

    return UserListResponse(items=user_responses, pagination=pagination)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user details by ID.

    Args:
        user_id: User UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        User details

    Raises:
        404: If user not found
    """
    try:
        user = await UserService.get_user_by_id(db, user_id)
        return UserResponse.model_validate(user)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
