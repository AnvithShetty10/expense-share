"""Split calculation strategies"""

from app.core.exceptions import ValidationError
from app.models.expense import SplitType
from app.services.split_strategies.base import (BaseSplitStrategy,
                                                ParticipantSplit)
from app.services.split_strategies.equal_split import EqualSplitStrategy
from app.services.split_strategies.manual_split import ManualSplitStrategy
from app.services.split_strategies.percentage_split import \
    PercentageSplitStrategy


def get_split_strategy(split_type: SplitType) -> BaseSplitStrategy:
    """
    Get appropriate split strategy based on split type.

    Args:
        split_type: Type of split (EQUAL, PERCENTAGE, or MANUAL)

    Returns:
        Instance of appropriate strategy

    Raises:
        ValidationError: If split_type is not recognized
    """
    strategies = {
        SplitType.EQUAL: EqualSplitStrategy(),
        SplitType.PERCENTAGE: PercentageSplitStrategy(),
        SplitType.MANUAL: ManualSplitStrategy(),
    }

    strategy = strategies.get(split_type)
    if strategy is None:
        raise ValidationError(f"Unknown split type: {split_type}")

    return strategy


__all__ = [
    "BaseSplitStrategy",
    "ParticipantSplit",
    "EqualSplitStrategy",
    "PercentageSplitStrategy",
    "ManualSplitStrategy",
    "get_split_strategy",
]
