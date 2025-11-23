"""User data access"""
from typing import Optional
from uuid import UUID
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for User database operations"""

    @staticmethod
    async def create(db: AsyncSession, user: User) -> User:
        """
        Create a new user.

        Args:
            db: Database session
            user: User object to create

        Returns:
            Created user
        """
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            User if found, None otherwise
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            db: Database session
            email: User email

        Returns:
            User if found, None otherwise
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            db: Database session
            username: Username

        Returns:
            User if found, None otherwise
        """
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email_or_username(db: AsyncSession, identifier: str) -> Optional[User]:
        """
        Get user by email or username.

        Args:
            db: Database session
            identifier: Email or username

        Returns:
            User if found, None otherwise
        """
        result = await db.execute(
            select(User).where(or_(User.email == identifier, User.username == identifier))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def check_email_exists(db: AsyncSession, email: str) -> bool:
        """
        Check if email already exists.

        Args:
            db: Database session
            email: Email to check

        Returns:
            True if exists, False otherwise
        """
        user = await UserRepository.get_by_email(db, email)
        return user is not None

    @staticmethod
    async def check_username_exists(db: AsyncSession, username: str) -> bool:
        """
        Check if username already exists.

        Args:
            db: Database session
            username: Username to check

        Returns:
            True if exists, False otherwise
        """
        user = await UserRepository.get_by_username(db, username)
        return user is not None

    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 20, search: Optional[str] = None) -> list[User]:
        """
        Get all users with pagination and optional search.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Optional search term for name or email

        Returns:
            List of users
        """
        query = select(User)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.username.ilike(search_pattern)
                )
            )

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count(db: AsyncSession, search: Optional[str] = None) -> int:
        """
        Count total users with optional search filter.

        Args:
            db: Database session
            search: Optional search term

        Returns:
            Total count of users
        """
        from sqlalchemy import func

        query = select(func.count(User.id))

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.username.ilike(search_pattern)
                )
            )

        result = await db.execute(query)
        return result.scalar_one()
