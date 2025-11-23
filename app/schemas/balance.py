"""Balance schemas"""
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserResponse
from app.schemas.expense import ExpenseListItem


class UserBalance(BaseModel):
    """Balance between current user and another user"""
    user: UserResponse
    amount: Decimal
    type: str  # "you_owe" or "owes_you"

    model_config = ConfigDict(from_attributes=True)


class BalanceSummary(BaseModel):
    """Summary of user's overall balance situation"""
    overall_balance: Decimal
    total_you_owe: Decimal
    total_owed_to_you: Decimal
    num_people_you_owe: int
    num_people_owe_you: int


class BalanceListResponse(BaseModel):
    """Response schema for list of balances"""
    balances: List[UserBalance]


class UserBalanceDetail(UserBalance):
    """Detailed balance with shared expense history"""
    shared_expenses: List[ExpenseListItem]
