"""Expense data access"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import Expense
from app.models.expense_participant import ExpenseParticipant


class ExpenseRepository:
    """Repository for Expense database operations"""

    @staticmethod
    async def create(db: AsyncSession, expense: Expense) -> Expense:
        """
        Create a new expense.

        Args:
            db: Database session
            expense: Expense object to create

        Returns:
            Created expense
        """
        db.add(expense)
        await db.flush()
        await db.refresh(expense)
        return expense

    @staticmethod
    async def get_by_id(db: AsyncSession, expense_id: UUID) -> Optional[Expense]:
        """
        Get expense by ID.

        Args:
            db: Database session
            expense_id: Expense UUID

        Returns:
            Expense if found, None otherwise
        """
        result = await db.execute(select(Expense).where(Expense.id == expense_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_with_participants(
        db: AsyncSession, expense_id: UUID
    ) -> Optional[Expense]:
        """
        Get expense with all participants eagerly loaded.

        Args:
            db: Database session
            expense_id: Expense UUID

        Returns:
            Expense with participants if found, None otherwise
        """
        result = await db.execute(
            select(Expense)
            .where(Expense.id == expense_id)
            .options(
                selectinload(Expense.participants).selectinload(
                    ExpenseParticipant.user
                ),
                selectinload(Expense.creator),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_expenses(
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        group_name: Optional[str] = None,
    ) -> List[Expense]:
        """
        Get all expenses involving a user with filters.

        Args:
            db: Database session
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            start_date: Optional start date filter
            end_date: Optional end date filter
            group_name: Optional group name filter

        Returns:
            List of expenses
        """
        # Subquery to find expenses where user is a participant
        participant_subquery = select(ExpenseParticipant.expense_id).where(
            ExpenseParticipant.user_id == user_id
        )

        query = select(Expense).where(Expense.id.in_(participant_subquery))

        # Apply filters
        if start_date:
            query = query.where(Expense.expense_date >= start_date)
        if end_date:
            query = query.where(Expense.expense_date <= end_date)
        if group_name:
            query = query.where(Expense.group_name == group_name)

        # Order by date descending (most recent first)
        query = query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Eager load participants and creator
        query = query.options(
            selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
            selectinload(Expense.creator),
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def is_user_participant(
        db: AsyncSession, expense_id: UUID, user_id: UUID
    ) -> bool:
        """
        Check if user is a participant in the expense.

        Args:
            db: Database session
            expense_id: Expense UUID
            user_id: User UUID

        Returns:
            True if user is participant, False otherwise
        """
        result = await db.execute(
            select(ExpenseParticipant).where(
                and_(
                    ExpenseParticipant.expense_id == expense_id,
                    ExpenseParticipant.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def delete(db: AsyncSession, expense_id: UUID) -> bool:
        """
        Delete an expense.

        Args:
            db: Database session
            expense_id: Expense UUID

        Returns:
            True if deleted, False if not found
        """
        expense = await ExpenseRepository.get_by_id(db, expense_id)
        if not expense:
            return False

        await db.delete(expense)
        await db.flush()
        return True

    @staticmethod
    async def count_user_expenses(
        db: AsyncSession,
        user_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        group_name: Optional[str] = None,
    ) -> int:
        """
        Count total expenses for a user with filters.

        Args:
            db: Database session
            user_id: User UUID
            start_date: Optional start date filter
            end_date: Optional end date filter
            group_name: Optional group name filter

        Returns:
            Total count of expenses
        """
        from sqlalchemy import func

        participant_subquery = select(ExpenseParticipant.expense_id).where(
            ExpenseParticipant.user_id == user_id
        )

        query = select(func.count(Expense.id)).where(
            Expense.id.in_(participant_subquery)
        )

        if start_date:
            query = query.where(Expense.expense_date >= start_date)
        if end_date:
            query = query.where(Expense.expense_date <= end_date)
        if group_name:
            query = query.where(Expense.group_name == group_name)

        result = await db.execute(query)
        return result.scalar_one()
