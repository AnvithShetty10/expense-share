"""Participant data access"""
from typing import List
from uuid import UUID
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense_participant import ExpenseParticipant


class ParticipantRepository:
    """Repository for ExpenseParticipant database operations"""

    @staticmethod
    async def create(db: AsyncSession, participant: ExpenseParticipant) -> ExpenseParticipant:
        """
        Create a new participant.

        Args:
            db: Database session
            participant: ExpenseParticipant object to create

        Returns:
            Created participant
        """
        db.add(participant)
        await db.flush()
        await db.refresh(participant)
        return participant

    @staticmethod
    async def create_batch(db: AsyncSession, participants: List[ExpenseParticipant]) -> List[ExpenseParticipant]:
        """
        Create multiple participants in a batch.

        Args:
            db: Database session
            participants: List of ExpenseParticipant objects

        Returns:
            List of created participants
        """
        db.add_all(participants)
        await db.flush()

        # Refresh all participants
        for participant in participants:
            await db.refresh(participant)

        return participants

    @staticmethod
    async def get_by_expense(db: AsyncSession, expense_id: UUID) -> List[ExpenseParticipant]:
        """
        Get all participants for an expense.

        Args:
            db: Database session
            expense_id: Expense UUID

        Returns:
            List of participants
        """
        result = await db.execute(
            select(ExpenseParticipant)
            .where(ExpenseParticipant.expense_id == expense_id)
            .options(selectinload(ExpenseParticipant.user))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_user(db: AsyncSession, user_id: UUID) -> List[ExpenseParticipant]:
        """
        Get all participations for a user.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            List of participants
        """
        result = await db.execute(
            select(ExpenseParticipant)
            .where(ExpenseParticipant.user_id == user_id)
            .options(
                selectinload(ExpenseParticipant.expense),
                selectinload(ExpenseParticipant.user)
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_user_participants_with_expenses(db: AsyncSession, user_id: UUID) -> List[ExpenseParticipant]:
        """
        Get all participations for a user with expense details loaded.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            List of participants with expense details
        """
        result = await db.execute(
            select(ExpenseParticipant)
            .where(ExpenseParticipant.user_id == user_id)
            .options(
                selectinload(ExpenseParticipant.expense).selectinload('participants').selectinload('user'),
                selectinload(ExpenseParticipant.user)
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_by_expense(db: AsyncSession, expense_id: UUID) -> int:
        """
        Delete all participants for an expense.

        Args:
            db: Database session
            expense_id: Expense UUID

        Returns:
            Number of participants deleted
        """
        result = await db.execute(
            sql_delete(ExpenseParticipant).where(ExpenseParticipant.expense_id == expense_id)
        )
        await db.flush()
        return result.rowcount
