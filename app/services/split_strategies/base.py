"""Base strategy interface"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List
from uuid import UUID

from pydantic import BaseModel


class ParticipantSplit(BaseModel):
    """Result of split calculation for a participant"""

    user_id: UUID
    amount_owed: Decimal


class BaseSplitStrategy(ABC):
    """Base class for split strategies"""

    @abstractmethod
    def calculate_splits(
        self, total_amount: Decimal, participant_data: List[dict]
    ) -> List[ParticipantSplit]:
        """
        Calculate split amounts for participants.

        Args:
            total_amount: Total expense amount
            participant_data: List of participant information

        Returns:
            List of ParticipantSplit objects with user_id and amount_owed
        """
        pass
