"""Balance calculation logic"""
import json
from typing import List, Dict, Optional
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from app.repositories.participant_repository import ParticipantRepository
from app.repositories.user_repository import UserRepository
from app.repositories.expense_repository import ExpenseRepository
from app.schemas.balance import UserBalance, BalanceSummary, UserBalanceDetail
from app.schemas.user import UserResponse
from app.schemas.expense import ExpenseListItem
from app.services.cache_service import CacheService
from app.core.exceptions import NotFoundError
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
        serializable = {str(user_id): str(amount) for user_id, amount in balances_dict.items()}
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
    async def _calculate_user_balances(user_id: UUID, db: AsyncSession) -> Dict[UUID, Decimal]:
        """
        Calculate balances for a user using simplified algorithm.

        Algorithm:
        1. Get all expenses involving the user
        2. For each expense, calculate contribution = amount_paid - amount_owed
        3. Group by other users and sum contributions
        4. Positive = others owe user, Negative = user owes others

        Args:
            user_id: User ID
            db: Database session

        Returns:
            Dictionary mapping other user IDs to net balance amounts
        """
        # Get all participations for the user with expense details
        participations = await ParticipantRepository.get_user_participants_with_expenses(db, user_id)

        # Dictionary to store net balance with each other user
        balances: Dict[UUID, Decimal] = defaultdict(lambda: Decimal('0'))

        # Process each expense
        for participation in participations:
            expense = participation.expense
            current_user_paid = participation.amount_paid
            current_user_owed = participation.amount_owed

            # Current user's contribution (positive = overpaid, negative = underpaid)
            contribution = current_user_paid - current_user_owed

            if contribution == 0:
                # User paid exactly what they owe, no balance change
                continue

            # Get all other participants in this expense
            other_participants = [p for p in expense.participants if p.user_id != user_id]

            if contribution > 0:
                # User overpaid - others owe them proportionally
                # Distribute the overpayment among others based on what they owe
                total_others_owe = sum(p.amount_owed for p in other_participants)

                if total_others_owe > 0:
                    for other_participant in other_participants:
                        # Proportion of overpayment this participant owes
                        proportion = other_participant.amount_owed / total_others_owe
                        amount_owed_to_user = round_decimal(contribution * proportion)
                        balances[other_participant.user_id] += amount_owed_to_user

            else:  # contribution < 0
                # User underpaid - they owe to payers proportionally
                user_owes = abs(contribution)

                # Find who paid in this expense (excluding current user)
                payers = [p for p in other_participants if p.amount_paid > 0]
                total_paid_by_others = sum(p.amount_paid for p in payers)

                if total_paid_by_others > 0:
                    for payer in payers:
                        # Proportion user owes to this payer
                        proportion = payer.amount_paid / total_paid_by_others
                        amount_owed_by_user = round_decimal(user_owes * proportion)
                        balances[payer.user_id] -= amount_owed_by_user

        # Round all final balances
        return {uid: round_decimal(amount) for uid, amount in balances.items() if amount != 0}

    @staticmethod
    async def get_user_balances(
        user_id: UUID,
        db: AsyncSession,
        use_cache: bool = True
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
                balances_dict = await BalanceService._calculate_user_balances(user_id, db)
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
                type=balance_type
            )
            user_balances.append(user_balance)

        # Sort by amount descending
        user_balances.sort(key=lambda b: b.amount, reverse=True)

        return user_balances

    @staticmethod
    async def get_balance_summary(
        user_id: UUID,
        db: AsyncSession,
        use_cache: bool = True
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
        total_owed_to_you = Decimal('0')
        total_you_owe = Decimal('0')
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
            num_people_owe_you=num_people_owe_you
        )

    @staticmethod
    async def get_balance_with_user(
        current_user_id: UUID,
        other_user_id: UUID,
        db: AsyncSession
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

        # Get all balances for current user
        all_balances = await BalanceService.get_user_balances(current_user_id, db)

        # Find balance with specific user
        balance_with_user = next(
            (b for b in all_balances if b.user.id == other_user_id),
            None
        )

        # If no balance found, create zero balance
        if not balance_with_user:
            balance_with_user = UserBalance(
                user=UserResponse.model_validate(other_user),
                amount=Decimal('0'),
                type="owes_you"
            )

        # Get shared expenses
        # Get all expenses for current user
        current_user_expenses, _ = await ExpenseRepository.get_user_expenses(
            db,
            current_user_id,
            skip=0,
            limit=1000  # Get all shared expenses
        )

        # Filter for expenses involving both users
        shared_expenses: List[ExpenseListItem] = []
        for expense in current_user_expenses:
            participant_user_ids = [p.user_id for p in expense.participants]

            if other_user_id in participant_user_ids:
                # Find current user's participation
                user_participant = next(
                    (p for p in expense.participants if p.user_id == current_user_id),
                    None
                )

                if user_participant:
                    net_amount = user_participant.amount_owed - user_participant.amount_paid
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
                        created_by=expense.creator
                    )
                    shared_expenses.append(expense_item)

        # Sort by date descending (most recent first)
        shared_expenses.sort(key=lambda e: e.date, reverse=True)

        return UserBalanceDetail(
            user=balance_with_user.user,
            amount=balance_with_user.amount,
            type=balance_with_user.type,
            shared_expenses=shared_expenses
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
