"""Expense participant model"""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Numeric, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ExpenseParticipant(Base):
    """Expense participant model linking users to expenses with payment details"""

    __tablename__ = "expense_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    expense_id = Column(UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    amount_paid = Column(Numeric(12, 2), default=0, nullable=False)
    amount_owed = Column(Numeric(12, 2), default=0, nullable=False)
    percentage = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint('expense_id', 'user_id', name='uq_expense_user'),
        CheckConstraint('amount_paid >= 0', name='check_amount_paid_non_negative'),
        CheckConstraint('amount_owed >= 0', name='check_amount_owed_non_negative'),
        CheckConstraint('amount_paid > 0 OR amount_owed > 0', name='check_at_least_one_amount'),
        CheckConstraint('percentage IS NULL OR (percentage >= 0 AND percentage <= 100)', name='check_percentage_range'),
    )

    # Relationships
    expense = relationship("Expense", back_populates="participants")
    user = relationship("User", back_populates="expense_participants")

    def __repr__(self) -> str:
        return f"<ExpenseParticipant(expense_id={self.expense_id}, user_id={self.user_id}, paid={self.amount_paid}, owed={self.amount_owed})>"
