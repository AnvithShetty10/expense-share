"""Equal split strategy"""

from decimal import Decimal
from typing import List

from app.services.split_strategies.base import (BaseSplitStrategy,
                                                ParticipantSplit)
from app.utils.decimal_utils import round_decimal, sum_decimals


class EqualSplitStrategy(BaseSplitStrategy):
    """Strategy for splitting expense equally among participants"""

    def calculate_splits(
        self, total_amount: Decimal, participant_data: List[dict]
    ) -> List[ParticipantSplit]:
        """
        Calculate equal split for all participants.

        Args:
            total_amount: Total expense amount
            participant_data: List of participant information (user_id, etc.)

        Returns:
            List of ParticipantSplit with equal amounts
        """
        num_participants = len(participant_data)

        if num_participants == 0:
            return []

        # Calculate base amount per person
        base_amount = total_amount / num_participants
        rounded_base = round_decimal(base_amount)

        # Create splits for all participants
        splits = []
        for participant in participant_data:
            splits.append(
                ParticipantSplit(
                    user_id=participant["user_id"], amount_owed=rounded_base
                )
            )

        # Handle rounding - adjust last participant to ensure total matches
        total_assigned = sum_decimals([split.amount_owed for split in splits])
        difference = total_amount - total_assigned

        if difference != 0:
            splits[-1].amount_owed += difference

        return splits
