"""Expense business logic"""
from typing import Optional, List
from uuid import UUID
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.expense_participant import ExpenseParticipant
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.participant_repository import ParticipantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services.split_strategies import get_split_strategy
from app.core.exceptions import ValidationError, NotFoundError, AuthorizationError
from app.utils.decimal_utils import sum_decimals


class ExpenseService:
    """Service for expense operations"""

    @staticmethod
    async def validate_participants_exist(db: AsyncSession, participant_data: list) -> None:
        """
        Validate that all participant user IDs exist.

        Args:
            db: Database session
            participant_data: List of participant input data

        Raises:
            ValidationError: If any user ID doesn't exist
        """
        for participant in participant_data:
            user = await UserRepository.get_by_id(db, participant.user_id)
            if not user:
                raise ValidationError(f"User with ID {participant.user_id} not found")

    @staticmethod
    async def validate_amounts(
        total_amount: Decimal,
        participant_data: list,
        calculated_splits: Optional[list] = None
    ) -> None:
        """
        Validate that amounts are correct.

        Args:
            total_amount: Total expense amount
            participant_data: List of participant input data
            calculated_splits: Optional list of calculated splits

        Raises:
            ValidationError: If amounts don't match
        """
        # Validate total paid equals total amount
        total_paid = sum_decimals([Decimal(str(p.amount_paid)) for p in participant_data])
        if abs(total_paid - total_amount) > Decimal('0.01'):
            raise ValidationError(
                f"Sum of amounts paid ({total_paid}) must equal total amount ({total_amount})"
            )

        # If we have calculated splits, validate total owed
        if calculated_splits:
            total_owed = sum_decimals([split.amount_owed for split in calculated_splits])
            if abs(total_owed - total_amount) > Decimal('0.01'):
                raise ValidationError(
                    f"Sum of amounts owed ({total_owed}) must equal total amount ({total_amount})"
                )

    @staticmethod
    async def create_expense(
        expense_data: ExpenseCreate,
        user_id: UUID,
        db: AsyncSession
    ) -> Expense:
        """
        Create a new expense.

        Args:
            expense_data: Expense creation data
            user_id: ID of user creating the expense
            db: Database session

        Returns:
            Created expense with participants

        Raises:
            ValidationError: If validation fails
        """
        # Validate all participant user IDs exist
        await ExpenseService.validate_participants_exist(db, expense_data.participants)

        # Get split strategy
        strategy = get_split_strategy(expense_data.split_type)

        # Calculate splits based on strategy
        participant_dicts = [p.model_dump() for p in expense_data.participants]
        calculated_splits = strategy.calculate_splits(
            expense_data.total_amount,
            participant_dicts
        )

        # Validate amounts
        await ExpenseService.validate_amounts(
            expense_data.total_amount,
            expense_data.participants,
            calculated_splits
        )

        # Begin transaction
        async with db.begin_nested():
            # Create expense
            expense = Expense(
                description=expense_data.description,
                total_amount=expense_data.total_amount,
                expense_date=expense_data.expense_date,
                created_by_user_id=user_id,
                group_name=expense_data.group_name,
                split_type=expense_data.split_type
            )

            created_expense = await ExpenseRepository.create(db, expense)

            # Create participants
            participants = []
            for participant_input, calculated_split in zip(expense_data.participants, calculated_splits):
                participant = ExpenseParticipant(
                    expense_id=created_expense.id,
                    user_id=participant_input.user_id,
                    amount_paid=participant_input.amount_paid,
                    amount_owed=calculated_split.amount_owed,
                    percentage=participant_input.percentage
                )
                participants.append(participant)

            await ParticipantRepository.create_batch(db, participants)

        await db.commit()

        # Return expense with participants loaded
        return await ExpenseRepository.get_with_participants(db, created_expense.id)

    @staticmethod
    async def get_user_expenses(
        user_id: UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        group_name: Optional[str] = None
    ) -> tuple[List[Expense], int]:
        """
        Get expenses for a user with pagination.

        Args:
            user_id: User ID
            db: Database session
            page: Page number (1-indexed)
            page_size: Items per page
            start_date: Optional start date filter
            end_date: Optional end date filter
            group_name: Optional group filter

        Returns:
            Tuple of (expenses list, total count)
        """
        skip = (page - 1) * page_size

        expenses = await ExpenseRepository.get_user_expenses(
            db,
            user_id,
            skip=skip,
            limit=page_size,
            start_date=start_date,
            end_date=end_date,
            group_name=group_name
        )

        total_count = await ExpenseRepository.count_user_expenses(
            db,
            user_id,
            start_date=start_date,
            end_date=end_date,
            group_name=group_name
        )

        return expenses, total_count

    @staticmethod
    async def get_expense_details(
        expense_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> Expense:
        """
        Get expense details with authorization check.

        Args:
            expense_id: Expense ID
            user_id: User ID requesting the expense
            db: Database session

        Returns:
            Expense with all details

        Raises:
            NotFoundError: If expense not found
            AuthorizationError: If user is not a participant
        """
        expense = await ExpenseRepository.get_with_participants(db, expense_id)

        if not expense:
            raise NotFoundError("Expense not found")

        # Check if user is a participant
        is_participant = await ExpenseRepository.is_user_participant(db, expense_id, user_id)
        if not is_participant:
            raise AuthorizationError("You are not authorized to view this expense")

        return expense

    @staticmethod
    async def update_expense(
        expense_id: UUID,
        expense_data: ExpenseUpdate,
        user_id: UUID,
        db: AsyncSession
    ) -> Expense:
        """
        Update an expense (creator only).

        Args:
            expense_id: Expense ID
            expense_data: Updated expense data
            user_id: User ID making the update
            db: Database session

        Returns:
            Updated expense

        Raises:
            NotFoundError: If expense not found
            AuthorizationError: If user is not the creator
            ValidationError: If validation fails
        """
        expense = await ExpenseRepository.get_by_id(db, expense_id)

        if not expense:
            raise NotFoundError("Expense not found")

        # Check if user is the creator
        if expense.created_by_user_id != user_id:
            raise AuthorizationError("Only the expense creator can update it")

        # Validate participants exist
        await ExpenseService.validate_participants_exist(db, expense_data.participants)

        # Get split strategy and calculate
        strategy = get_split_strategy(expense_data.split_type)
        participant_dicts = [p.model_dump() for p in expense_data.participants]
        calculated_splits = strategy.calculate_splits(
            expense_data.total_amount,
            participant_dicts
        )

        # Validate amounts
        await ExpenseService.validate_amounts(
            expense_data.total_amount,
            expense_data.participants,
            calculated_splits
        )

        # Begin transaction
        async with db.begin_nested():
            # Update expense fields
            expense.description = expense_data.description
            expense.total_amount = expense_data.total_amount
            expense.expense_date = expense_data.expense_date
            expense.group_name = expense_data.group_name
            expense.split_type = expense_data.split_type

            # Delete old participants
            await ParticipantRepository.delete_by_expense(db, expense_id)

            # Create new participants
            participants = []
            for participant_input, calculated_split in zip(expense_data.participants, calculated_splits):
                participant = ExpenseParticipant(
                    expense_id=expense_id,
                    user_id=participant_input.user_id,
                    amount_paid=participant_input.amount_paid,
                    amount_owed=calculated_split.amount_owed,
                    percentage=participant_input.percentage
                )
                participants.append(participant)

            await ParticipantRepository.create_batch(db, participants)

        await db.commit()

        # Return updated expense with participants
        return await ExpenseRepository.get_with_participants(db, expense_id)

    @staticmethod
    async def delete_expense(
        expense_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> bool:
        """
        Delete an expense (creator only).

        Args:
            expense_id: Expense ID
            user_id: User ID making the deletion
            db: Database session

        Returns:
            True if deleted

        Raises:
            NotFoundError: If expense not found
            AuthorizationError: If user is not the creator
        """
        expense = await ExpenseRepository.get_by_id(db, expense_id)

        if not expense:
            raise NotFoundError("Expense not found")

        # Check if user is the creator
        if expense.created_by_user_id != user_id:
            raise AuthorizationError("Only the expense creator can delete it")

        # Delete expense (participants will be cascade deleted)
        await ExpenseRepository.delete(db, expense_id)
        await db.commit()

        return True
