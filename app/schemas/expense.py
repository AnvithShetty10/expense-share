"""Expense schemas"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.expense import SplitType
from app.schemas.common import PaginationMeta
from app.schemas.user import UserResponse


class ParticipantInput(BaseModel):
    """Input schema for expense participant"""

    user_id: UUID
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0)
    amount_owed: Optional[Decimal] = Field(default=None, ge=0)
    percentage: Optional[Decimal] = Field(default=None, ge=0, le=100)

    @field_validator("amount_paid", "amount_owed", "percentage", mode="before")
    @classmethod
    def convert_to_decimal(cls, v):
        """Convert numeric values to Decimal"""
        if v is None:
            return v
        return Decimal(str(v))


class ExpenseBase(BaseModel):
    """Base expense schema"""

    description: str = Field(..., max_length=500, min_length=1)
    total_amount: Decimal = Field(..., gt=0)
    expense_date: date
    group_name: Optional[str] = Field(default=None, max_length=255)
    split_type: SplitType

    @field_validator("total_amount", mode="before")
    @classmethod
    def convert_total_amount(cls, v):
        """Convert total_amount to Decimal"""
        return Decimal(str(v))


class ExpenseCreate(ExpenseBase):
    """Schema for creating an expense"""

    participants: List[ParticipantInput] = Field(..., min_length=1)

    @field_validator("participants")
    @classmethod
    def validate_participants(cls, v):
        """Validate that there is at least one participant"""
        if not v or len(v) == 0:
            raise ValueError("At least one participant is required")
        return v


class ExpenseUpdate(ExpenseBase):
    """Schema for updating an expense"""

    participants: List[ParticipantInput] = Field(..., min_length=1)


class ParticipantResponse(BaseModel):
    """Response schema for expense participant"""

    user: UserResponse
    amount_paid: Decimal
    amount_owed: Decimal
    percentage: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseResponse(ExpenseBase):
    """Complete expense response schema"""

    id: UUID
    currency: str
    created_by: UserResponse = Field(..., validation_alias="creator")
    participants: List[ParticipantResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExpenseListItem(BaseModel):
    """Schema for expense in list view"""

    id: UUID
    date: date
    group_name: Optional[str]
    description: str
    total_amount: Decimal
    your_share: Decimal
    share_type: str  # "credit" or "debit"
    created_by: UserResponse = Field(..., validation_alias="creator")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExpenseListResponse(BaseModel):
    """Response schema for expense list"""

    items: List[ExpenseListItem]
    pagination: PaginationMeta
