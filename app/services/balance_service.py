"""Balance calculation logic"""

import json
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.participant_repository import ParticipantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.balance import BalanceSummary, UserBalance, UserBalanceDetail
from app.schemas.expense import ExpenseListItem
from app.schemas.user import UserResponse
from app.services.cache_service import CacheService
from app.utils.decimal_utils import round_decimal


class BalanceService:
    """Service for balance calculation operations"""

    @staticmethod
    def _serialize_balances(balances_dict: Dict[UUID, Decimal]) -> str:
        """
        Serialize balances dictionary to JSON.

        Args:
            balances_dict: Dictionary mapping user IDs to balance amounts

        Returns:
            JSON string
        """
        serializable = {
            str(user_id): str(amount) for user_id, amount in balances_dict.items()
        }
        return json.dumps(serializable)

    @staticmethod
    def _deserialize_balances(json_str: str) -> Dict[UUID, Decimal]:
        """
        Deserialize balances from JSON.

        Args:
            json_str: JSON string

        Returns:
            Dictionary mapping user IDs to balance amounts
        """
        data = json.loads(json_str)
        return {UUID(user_id): Decimal(amount) for user_id, amount in data.items()}

    @staticmethod
    async def _calculate_user_balances(
        user_id: UUID, db: AsyncSession
    ) -> Dict[UUID, Decimal]:
        """
        Calculate balances for a user with all other users they've shared expenses with.

        Uses pairwise calculation to ensure consistency with get_balance_with_user.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            Dictionary mapping other user IDs to net balance amounts
            (positive = other user owes this user, negative = this user owes other user)
        """
        # Get all participations for the user with expense details
        participations = (
            await ParticipantRepository.get_user_participants_with_expenses(db, user_id)
        )

        # Get unique set of other users involved in expenses
        other_user_ids: set[UUID] = set()
        for participation in participations:
            for participant in participation.expense.participants:
                if participant.user_id != user_id:
                    other_user_ids.add(participant.user_id)

        # Calculate pairwise balance with each user
        balances: Dict[UUID, Decimal] = {}
        for other_user_id in other_user_ids:
            balance = await BalanceService._calculate_pairwise_balance(
                user_id, other_user_id, db
            )
            if balance != 0:
                balances[other_user_id] = balance

        return balances

    @staticmethod
    async def _calculate_pairwise_balance(
        user1_id: UUID, user2_id: UUID, db: AsyncSession
    ) -> Decimal:
        """
        Calculate the direct balance between two specific users.
        Positive means user2 owes user1, negative means user1 owes user2.

        This method is symmetric: _calculate_pairwise_balance(A, B) = -_calculate_pairwise_balance(B, A)

        Args:
            user1_id: First user ID
            user2_id: Second user ID
            db: Database session

        Returns:
            Balance amount (positive = user2 owes user1)
        """
        # Get all expenses involving user1
        user1_expenses = await ExpenseRepository.get_user_expenses(
            db, user1_id, skip=0, limit=10000
        )

        total_balance = Decimal("0")

        # Process each expense involving both users
        for expense in user1_expenses:
            participant_ids = [p.user_id for p in expense.participants]

            # Skip if user2 not in this expense
            if user2_id not in participant_ids:
                continue

            # Find both participants
            user1_participant = next(
                (p for p in expense.participants if p.user_id == user1_id), None
            )
            user2_participant = next(
                (p for p in expense.participants if p.user_id == user2_id), None
            )

            if not user1_participant or not user2_participant:
                continue

            # Calculate how much user1 paid for user2's share
            # and how much user2 paid for user1's share
            user1_paid = user1_participant.amount_paid
            user1_owed = user1_participant.amount_owed
            user2_paid = user2_participant.amount_paid
            user2_owed = user2_participant.amount_owed

            # User1's overpayment (or negative if underpaid)
            user1_contribution = user1_paid - user1_owed
            user2_contribution = user2_paid - user2_owed

            # Calculate total overpayments and underpayments in this expense
            total_overpayment = Decimal("0")
            total_underpayment = Decimal("0")

            for participant in expense.participants:
                contrib = participant.amount_paid - participant.amount_owed
                if contrib > 0:
                    total_overpayment += contrib
                elif contrib < 0:
                    total_underpayment += abs(contrib)

            # If user1 overpaid and user2 underpaid (or vice versa)
            if user1_contribution > 0 and user2_contribution < 0:
                # user1 covered some of user2's share
                user2_underpayment = abs(user2_contribution)
                if total_underpayment > 0:
                    # Portion of user1's overpayment that went to user2
                    portion = user2_underpayment / total_underpayment
                    amount = user1_contribution * portion
                    total_balance += amount

            elif user1_contribution < 0 and user2_contribution > 0:
                # user2 covered some of user1's share
                user1_underpayment = abs(user1_contribution)
                if total_underpayment > 0:
                    # Portion of user2's overpayment that went to user1
                    portion = user1_underpayment / total_underpayment
                    amount = user2_contribution * portion
                    total_balance -= amount

        return round_decimal(total_balance)

    @staticmethod
    async def get_user_balances(
        user_id: UUID, db: AsyncSession, use_cache: bool = True
    ) -> List[UserBalance]:
        """
        Get all balances for a user.

        Args:
            user_id: User ID
            db: Database session
            use_cache: Whether to use cache (default: True)

        Returns:
            List of UserBalance objects
        """
        balances_dict: Dict[UUID, Decimal]

        # Try to get from cache
        if use_cache:
            cache_key = f"balance:{user_id}"
            cached_data = await CacheService.get(cache_key)

            if cached_data:
                balances_dict = BalanceService._deserialize_balances(cached_data)
            else:
                # Calculate and cache
                balances_dict = await BalanceService._calculate_user_balances(
                    user_id, db
                )
                serialized = BalanceService._serialize_balances(balances_dict)
                await CacheService.set(cache_key, serialized, ttl=3600)
        else:
            # Calculate without cache
            balances_dict = await BalanceService._calculate_user_balances(user_id, db)

        # Convert to UserBalance objects
        user_balances: List[UserBalance] = []

        for other_user_id, amount in balances_dict.items():
            # Get user details
            other_user = await UserRepository.get_by_id(db, other_user_id)
            if not other_user:
                continue

            # Determine balance type
            if amount > 0:
                balance_type = "owes_you"
                balance_amount = amount
            else:
                balance_type = "you_owe"
                balance_amount = abs(amount)

            user_balance = UserBalance(
                user=UserResponse.model_validate(other_user),
                amount=balance_amount,
                type=balance_type,
            )
            user_balances.append(user_balance)

        # Sort by amount descending
        user_balances.sort(key=lambda b: b.amount, reverse=True)

        return user_balances

    @staticmethod
    async def get_balance_summary(
        user_id: UUID, db: AsyncSession, use_cache: bool = True
    ) -> BalanceSummary:
        """
        Get balance summary for a user.

        Args:
            user_id: User ID
            db: Database session
            use_cache: Whether to use cache (default: True)

        Returns:
            BalanceSummary object
        """
        # Get all balances
        user_balances = await BalanceService.get_user_balances(user_id, db, use_cache)

        # Calculate summary statistics
        total_owed_to_you = Decimal("0")
        total_you_owe = Decimal("0")
        num_people_owe_you = 0
        num_people_you_owe = 0

        for balance in user_balances:
            if balance.type == "owes_you":
                total_owed_to_you += balance.amount
                num_people_owe_you += 1
            else:  # you_owe
                total_you_owe += balance.amount
                num_people_you_owe += 1

        overall_balance = total_owed_to_you - total_you_owe

        return BalanceSummary(
            overall_balance=round_decimal(overall_balance),
            total_you_owe=round_decimal(total_you_owe),
            total_owed_to_you=round_decimal(total_owed_to_you),
            num_people_you_owe=num_people_you_owe,
            num_people_owe_you=num_people_owe_you,
        )

    @staticmethod
    async def get_balance_with_user(
        current_user_id: UUID, other_user_id: UUID, db: AsyncSession
    ) -> UserBalanceDetail:
        """
        Get balance between current user and another specific user.

        Args:
            current_user_id: Current user ID
            other_user_id: Other user ID
            db: Database session

        Returns:
            UserBalanceDetail with shared expense history

        Raises:
            NotFoundError: If other user not found
        """
        # Validate other user exists
        other_user = await UserRepository.get_by_id(db, other_user_id)
        if not other_user:
            raise NotFoundError(f"User with ID {other_user_id} not found")

        # Calculate direct balance between the two users
        # This ensures symmetry: balance(A,B) = -balance(B,A)
        balance_amount = await BalanceService._calculate_pairwise_balance(
            current_user_id, other_user_id, db
        )

        # Determine balance type
        if balance_amount > 0:
            balance_type = "owes_you"
            display_amount = balance_amount
        elif balance_amount < 0:
            balance_type = "you_owe"
            display_amount = abs(balance_amount)
        else:
            balance_type = "owes_you"
            display_amount = Decimal("0")

        balance_with_user = UserBalance(
            user=UserResponse.model_validate(other_user),
            amount=display_amount,
            type=balance_type,
        )

        # Get shared expenses
        # Get all expenses for current user
        current_user_expenses = await ExpenseRepository.get_user_expenses(
            db, current_user_id, skip=0, limit=1000  # Get all shared expenses
        )

        # Filter for expenses involving both users
        shared_expenses: List[ExpenseListItem] = []
        for expense in current_user_expenses:
            participant_user_ids = [p.user_id for p in expense.participants]

            if other_user_id in participant_user_ids:
                # Find current user's participation
                user_participant = next(
                    (p for p in expense.participants if p.user_id == current_user_id),
                    None,
                )

                if user_participant:
                    net_amount = (
                        user_participant.amount_owed - user_participant.amount_paid
                    )
                    share_type = "debit" if net_amount > 0 else "credit"
                    your_share = abs(net_amount)

                    expense_item = ExpenseListItem(
                        id=expense.id,
                        date=expense.expense_date,
                        group_name=expense.group_name,
                        description=expense.description,
                        total_amount=expense.total_amount,
                        your_share=your_share,
                        share_type=share_type,
                        created_by=expense.creator,
                    )
                    shared_expenses.append(expense_item)

        # Sort by date descending (most recent first)
        shared_expenses.sort(key=lambda e: e.date, reverse=True)

        return UserBalanceDetail(
            user=balance_with_user.user,
            amount=balance_with_user.amount,
            type=balance_with_user.type,
            shared_expenses=shared_expenses,
        )

    @staticmethod
    async def invalidate_balances_for_users(user_ids: List[UUID]) -> bool:
        """
        Invalidate cached balances for multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            True if successful
        """
        if not user_ids:
            return True

        cache_keys = [f"balance:{user_id}" for user_id in user_ids]
        return await CacheService.delete_multiple(cache_keys)
