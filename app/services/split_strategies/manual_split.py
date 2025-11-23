"""Manual split strategy"""
from decimal import Decimal
from typing import List

from app.services.split_strategies.base import BaseSplitStrategy, ParticipantSplit
from app.utils.decimal_utils import sum_decimals
from app.core.exceptions import ValidationError


class ManualSplitStrategy(BaseSplitStrategy):
    """Strategy for manual split with specified amounts"""

    def calculate_splits(
        self,
        total_amount: Decimal,
        participant_data: List[dict]
    ) -> List[ParticipantSplit]:
        """
        Use manually specified amounts for split.

        Args:
            total_amount: Total expense amount
            participant_data: List of dicts with user_id and amount_owed

        Returns:
            List of ParticipantSplit with specified amounts

        Raises:
            ValidationError: If manual amounts don't sum to total_amount
        """
        if not participant_data:
            return []

        # Create splits from provided amounts
        splits = []
        for participant in participant_data:
            amount_owed = Decimal(str(participant.get('amount_owed', 0)))

            if amount_owed < 0:
                raise ValidationError(
                    f"Amount owed cannot be negative, got {amount_owed}"
                )

            splits.append(ParticipantSplit(
                user_id=participant['user_id'],
                amount_owed=amount_owed
            ))

        # Validate that amounts sum to total
        total_assigned = sum_decimals([split.amount_owed for split in splits])

        # Allow small rounding difference (0.01)
        difference = abs(total_amount - total_assigned)
        if difference > Decimal('0.01'):
            raise ValidationError(
                f"Sum of manual amounts ({total_assigned}) must equal total amount ({total_amount})"
            )

        return splits
