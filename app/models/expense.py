"""Expense model"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Numeric, String, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class SplitType(str, enum.Enum):
    """Enum for split types"""
    EQUAL = "EQUAL"
    PERCENTAGE = "PERCENTAGE"
    MANUAL = "MANUAL"


class Expense(Base):
    """Expense model for tracking shared expenses"""

    __tablename__ = "expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    description = Column(String(500), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    expense_date = Column(Date, nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    group_name = Column(String(255), nullable=True)
    split_type = Column(Enum(SplitType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint('total_amount > 0', name='check_total_amount_positive'),
    )

    # Relationships
    creator = relationship("User", back_populates="expenses_created", foreign_keys=[created_by_user_id])
    participants = relationship("ExpenseParticipant", back_populates="expense", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Expense(id={self.id}, description={self.description}, total_amount={self.total_amount})>"
