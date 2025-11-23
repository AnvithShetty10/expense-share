"""Percentage split strategy"""

from decimal import Decimal
from typing import List

from app.core.exceptions import ValidationError
from app.services.split_strategies.base import (BaseSplitStrategy,
                                                ParticipantSplit)
from app.utils.decimal_utils import round_decimal, sum_decimals


class PercentageSplitStrategy(BaseSplitStrategy):
    """Strategy for splitting expense by percentage"""

    def calculate_splits(
        self, total_amount: Decimal, participant_data: List[dict]
    ) -> List[ParticipantSplit]:
        """
        Calculate percentage-based split for participants.

        Args:
            total_amount: Total expense amount
            participant_data: List of dicts with user_id and percentage

        Returns:
            List of ParticipantSplit with calculated amounts

        Raises:
            ValidationError: If percentages don't sum to 100
        """
        if not participant_data:
            return []

        # Validate percentages sum to 100
        total_percentage = sum(
            Decimal(str(p.get("percentage", 0) or 0)) for p in participant_data
        )

        if abs(total_percentage - Decimal("100")) > Decimal("0.01"):
            raise ValidationError(
                f"Percentages must sum to 100%, got {total_percentage}%"
            )

        # Validate individual percentages
        for participant in participant_data:
            percentage = Decimal(str(participant.get("percentage", 0)))
            if percentage < 0 or percentage > 100:
                raise ValidationError(
                    f"Percentage must be between 0 and 100, got {percentage}"
                )

        # Calculate amounts
        splits = []
        for participant in participant_data:
            percentage = Decimal(str(participant["percentage"]))
            amount = (total_amount * percentage) / Decimal("100")
            rounded_amount = round_decimal(amount)

            splits.append(
                ParticipantSplit(
                    user_id=participant["user_id"], amount_owed=rounded_amount
                )
            )

        # Handle rounding - adjust last participant to ensure total matches
        total_assigned = sum_decimals([split.amount_owed for split in splits])
        difference = total_amount - total_assigned

        if difference != 0:
            splits[-1].amount_owed += difference

        return splits
