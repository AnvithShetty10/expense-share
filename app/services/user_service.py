"""User business logic"""
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.cache_service import CacheService
from app.core.exceptions import NotFoundError


class UserService:
    """Service for user operations"""

    @staticmethod
    def _get_user_count_cache_key(search: Optional[str] = None) -> str:
        """
        Get cache key for user count.

        Args:
            search: Optional search term

        Returns:
            Cache key string
        """
        if search:
            # Include search term in cache key
            return f"user_count:search:{search}"
        return "user_count:all"

    @staticmethod
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        use_cache: bool = True
    ) -> Tuple[List[User], int]:
        """
        Get list of users with pagination and search.

        Args:
            db: Database session
            page: Page number (1-indexed)
            page_size: Items per page
            search: Optional search query (searches username, email, full_name)
            use_cache: Whether to use cache for count (default: True)

        Returns:
            Tuple of (users list, total count)
        """
        skip = (page - 1) * page_size

        # Get users
        users = await UserRepository.get_all(
            db,
            skip=skip,
            limit=page_size,
            search=search
        )

        # Get total count (with caching)
        total_count: int

        if use_cache:
            cache_key = UserService._get_user_count_cache_key(search)
            cached_count = await CacheService.get(cache_key)

            if cached_count:
                total_count = int(cached_count)
            else:
                # Calculate and cache
                total_count = await UserRepository.count(db, search=search)
                await CacheService.set(cache_key, str(total_count), ttl=3600)
        else:
            # Calculate without cache
            total_count = await UserRepository.count(db, search=search)

        return users, total_count

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: UUID
    ) -> User:
        """
        Get user by ID.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            User object

        Raises:
            NotFoundError: If user not found
        """
        user = await UserRepository.get_by_id(db, user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        return user

    @staticmethod
    async def invalidate_user_count_cache() -> bool:
        """
        Invalidate all user count caches.

        This should be called when a new user is registered.
        We invalidate all variants (with and without search) by deleting
        the base key. In production, you might want to use Redis SCAN
        to find and delete all matching keys.

        Returns:
            True if successful
        """
        # For now, we'll just invalidate the main count
        # In production, you'd want to use Redis SCAN to find all user_count:* keys
        cache_key = UserService._get_user_count_cache_key(search=None)
        return await CacheService.delete(cache_key)
