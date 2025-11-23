"""Unit tests for expense business logic"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.models.expense import SplitType
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ParticipantInput
from app.services.expense_service import ExpenseService


@pytest.fixture
def mock_db():
    """Create mock database session"""
    db = AsyncMock()
    # Mock begin_nested to return an async context manager (not a coroutine)
    nested_transaction = MagicMock()
    nested_transaction.__aenter__ = AsyncMock(return_value=nested_transaction)
    nested_transaction.__aexit__ = AsyncMock(return_value=None)
    db.begin_nested = MagicMock(return_value=nested_transaction)
    return db


@pytest.fixture
def test_user_id():
    """Test user ID"""
    return uuid4()


@pytest.fixture
def other_user_id():
    """Other user ID"""
    return uuid4()


class TestValidateParticipantsExist:
    """Test participant existence validation"""

    @pytest.mark.asyncio
    @patch("app.services.expense_service.UserRepository")
    async def test_validate_participants_exist_success(
        self, mock_user_repo, mock_db, test_user_id, other_user_id
    ):
        """Test successful participant validation when all users exist"""
        # Setup mocks - both users exist (must return awaitables)
        async def get_by_id_side_effect(db, user_id):
            if user_id == test_user_id:
                return User(id=test_user_id)
            elif user_id == other_user_id:
                return User(id=other_user_id)

        mock_user_repo.get_by_id = AsyncMock(side_effect=get_by_id_side_effect)

        participants = [
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("100.00")),
            ParticipantInput(user_id=other_user_id, amount_paid=Decimal("0.00")),
        ]

        # Should not raise
        await ExpenseService.validate_participants_exist(mock_db, participants)

        assert mock_user_repo.get_by_id.call_count == 2

    @pytest.mark.asyncio
    async def test_validate_participants_exist_empty(self, mock_db):
        """Test validation with no participants - should not raise (validated at schema level)"""
        # Empty list doesn't raise in the service method itself
        # This is validated at the Pydantic schema level with min_length=1
        await ExpenseService.validate_participants_exist(mock_db, [])

    @pytest.mark.asyncio
    @patch("app.services.expense_service.UserRepository")
    async def test_validate_participants_exist_user_not_found(
        self, mock_user_repo, mock_db, test_user_id
    ):
        """Test validation fails when user doesn't exist"""
        # Setup mock - user not found (must return awaitable)
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        participants = [ParticipantInput(user_id=test_user_id, amount_paid=Decimal("100.00"))]

        with pytest.raises(ValidationError, match="User with ID.*not found"):
            await ExpenseService.validate_participants_exist(mock_db, participants)

    @pytest.mark.asyncio
    @patch("app.services.expense_service.UserRepository")
    async def test_validate_participants_exist_multiple_users(
        self, mock_user_repo, mock_db, test_user_id, other_user_id
    ):
        """Test validation with multiple participants - including duplicate IDs (no validation for duplicates at this level)"""
        # This method doesn't check for duplicates - just validates existence (must return awaitable)
        mock_user_repo.get_by_id = AsyncMock(return_value=User(id=test_user_id))

        participants = [
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("50.00")),
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("50.00")),  # Duplicate allowed here
        ]

        # Should not raise - duplicate validation happens elsewhere
        await ExpenseService.validate_participants_exist(mock_db, participants)
        assert mock_user_repo.get_by_id.call_count == 2


class TestValidateAmounts:
    """Test amount validation"""

    @pytest.mark.asyncio
    async def test_validate_amounts_correct(self, test_user_id, other_user_id):
        """Test validation passes when amounts match"""
        total = Decimal("100.00")
        participants = [
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("60.00")),
            ParticipantInput(user_id=other_user_id, amount_paid=Decimal("40.00")),
        ]

        # Should not raise
        await ExpenseService.validate_amounts(total, participants)

    @pytest.mark.asyncio
    async def test_validate_amounts_mismatch(self, test_user_id, other_user_id):
        """Test validation fails when amounts don't match"""
        total = Decimal("100.00")
        participants = [
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("50.00")),
            ParticipantInput(user_id=other_user_id, amount_paid=Decimal("30.00")),  # Only 80 total
        ]

        with pytest.raises(
            ValidationError, match="Sum of amounts paid.*must equal total amount"
        ):
            await ExpenseService.validate_amounts(total, participants)

    @pytest.mark.asyncio
    async def test_validate_amounts_with_calculated_splits(self, test_user_id, other_user_id):
        """Test validation with calculated splits"""
        total = Decimal("100.00")
        participants = [
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("100.00")),
            ParticipantInput(user_id=other_user_id, amount_paid=Decimal("0.00")),
        ]

        # Mock calculated splits
        mock_split1 = MagicMock()
        mock_split1.amount_owed = Decimal("50.00")
        mock_split2 = MagicMock()
        mock_split2.amount_owed = Decimal("50.00")
        calculated_splits = [mock_split1, mock_split2]

        # Should not raise
        await ExpenseService.validate_amounts(total, participants, calculated_splits)

    @pytest.mark.asyncio
    async def test_validate_amounts_split_mismatch(self, test_user_id, other_user_id):
        """Test validation fails when calculated splits don't match total"""
        total = Decimal("100.00")
        participants = [
            ParticipantInput(user_id=test_user_id, amount_paid=Decimal("100.00")),
            ParticipantInput(user_id=other_user_id, amount_paid=Decimal("0.00")),
        ]

        # Mock calculated splits that don't add up
        mock_split1 = MagicMock()
        mock_split1.amount_owed = Decimal("40.00")
        mock_split2 = MagicMock()
        mock_split2.amount_owed = Decimal("40.00")  # Only 80 total
        calculated_splits = [mock_split1, mock_split2]

        with pytest.raises(
            ValidationError, match="Sum of amounts owed.*must equal total amount"
        ):
            await ExpenseService.validate_amounts(total, participants, calculated_splits)


class TestCreateExpense:
    """Test expense creation"""

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService")
    @patch("app.services.expense_service.ParticipantRepository")
    @patch("app.services.expense_service.ExpenseService.validate_participants_exist")
    @patch("app.services.expense_service.ExpenseService.validate_amounts")
    @patch("app.services.expense_service.get_split_strategy")
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_create_expense_success(
        self,
        mock_expense_repo,
        mock_get_strategy,
        mock_validate_amounts,
        mock_validate_participants,
        mock_participant_repo,
        mock_balance_service,
        mock_db,
        test_user_id,
        other_user_id,
    ):
        """Test successful expense creation"""
        # Setup mocks
        mock_strategy = MagicMock()
        mock_split1 = MagicMock(amount_owed=Decimal("50.00"))
        mock_split2 = MagicMock(amount_owed=Decimal("50.00"))
        mock_strategy.calculate_splits.return_value = [mock_split1, mock_split2]
        mock_get_strategy.return_value = mock_strategy

        mock_created_expense = MagicMock()
        expense_id = uuid4()
        mock_created_expense.id = expense_id
        mock_expense_repo.create = AsyncMock(return_value=mock_created_expense)

        mock_final_expense = MagicMock()
        mock_final_expense.id = expense_id
        mock_expense_repo.get_with_participants = AsyncMock(return_value=mock_final_expense)

        mock_balance_service.invalidate_balances_for_users = AsyncMock(return_value=True)
        mock_participant_repo.create_batch = AsyncMock(return_value=None)

        expense_data = ExpenseCreate(
            description="Team Lunch",
            total_amount=Decimal("100.00"),
            expense_date="2024-01-15",
            group_name="Work",
            split_type=SplitType.EQUAL,
            participants=[
                ParticipantInput(
                    user_id=test_user_id,
                    amount_paid=Decimal("100.00"),
                ),
                ParticipantInput(
                    user_id=other_user_id,
                    amount_paid=Decimal("0.00"),
                ),
            ],
        )

        # Create expense
        result = await ExpenseService.create_expense(expense_data, test_user_id, mock_db)

        # Assertions
        assert result == mock_final_expense
        mock_validate_participants.assert_called_once()
        mock_validate_amounts.assert_called_once()
        mock_strategy.calculate_splits.assert_called_once()
        mock_expense_repo.create.assert_called_once()
        mock_participant_repo.create_batch.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_expense_repo.get_with_participants.assert_called_once_with(mock_db, expense_id)
        mock_balance_service.invalidate_balances_for_users.assert_called_once()


class TestGetExpenseDetails:
    """Test getting expense details"""

    @pytest.mark.asyncio
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_get_expense_details_success(
        self, mock_expense_repo, mock_db, test_user_id
    ):
        """Test successfully getting expense details"""
        expense_id = uuid4()
        mock_expense = MagicMock()
        mock_expense.id = expense_id

        mock_expense_repo.get_with_participants = AsyncMock(return_value=mock_expense)
        mock_expense_repo.is_user_participant = AsyncMock(return_value=True)

        result = await ExpenseService.get_expense_details(
            expense_id, test_user_id, mock_db
        )

        assert result == mock_expense
        mock_expense_repo.get_with_participants.assert_called_once_with(mock_db, expense_id)
        mock_expense_repo.is_user_participant.assert_called_once_with(mock_db, expense_id, test_user_id)

    @pytest.mark.asyncio
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_get_expense_details_not_found(
        self, mock_expense_repo, mock_db, test_user_id
    ):
        """Test expense not found"""
        expense_id = uuid4()
        mock_expense_repo.get_with_participants = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="Expense not found"):
            await ExpenseService.get_expense_details(expense_id, test_user_id, mock_db)

    @pytest.mark.asyncio
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_get_expense_details_not_participant(
        self, mock_expense_repo, mock_db, test_user_id
    ):
        """Test user is not a participant"""
        expense_id = uuid4()

        mock_expense = MagicMock()
        mock_expense.id = expense_id

        mock_expense_repo.get_with_participants = AsyncMock(return_value=mock_expense)
        mock_expense_repo.is_user_participant = AsyncMock(return_value=False)  # Not a participant

        with pytest.raises(
            AuthorizationError, match="You are not authorized to view this expense"
        ):
            await ExpenseService.get_expense_details(expense_id, test_user_id, mock_db)


class TestDeleteExpense:
    """Test expense deletion"""

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService")
    @patch("app.services.expense_service.ParticipantRepository")
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_delete_expense_success(
        self, mock_expense_repo, mock_participant_repo, mock_balance_service, mock_db, test_user_id
    ):
        """Test successful expense deletion"""
        expense_id = uuid4()

        mock_expense = MagicMock()
        mock_expense.id = expense_id
        mock_expense.created_by_user_id = test_user_id

        mock_participant = MagicMock()
        mock_participant.user_id = test_user_id

        mock_expense_repo.get_by_id = AsyncMock(return_value=mock_expense)
        mock_participant_repo.get_by_expense = AsyncMock(return_value=[mock_participant])
        mock_expense_repo.delete = AsyncMock(return_value=None)
        mock_balance_service.invalidate_balances_for_users = AsyncMock(return_value=True)

        result = await ExpenseService.delete_expense(expense_id, test_user_id, mock_db)

        assert result is True
        mock_expense_repo.delete.assert_called_once_with(mock_db, expense_id)
        mock_db.commit.assert_called_once()
        mock_balance_service.invalidate_balances_for_users.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_delete_expense_not_found(
        self, mock_expense_repo, mock_db, test_user_id
    ):
        """Test deleting non-existent expense"""
        expense_id = uuid4()
        mock_expense_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="Expense not found"):
            await ExpenseService.delete_expense(expense_id, test_user_id, mock_db)

    @pytest.mark.asyncio
    @patch("app.services.expense_service.ParticipantRepository")
    @patch("app.services.expense_service.ExpenseRepository")
    async def test_delete_expense_not_creator(
        self, mock_expense_repo, mock_participant_repo, mock_db, test_user_id
    ):
        """Test non-creator cannot delete expense"""
        expense_id = uuid4()
        creator_id = uuid4()

        mock_expense = MagicMock()
        mock_expense.id = expense_id
        mock_expense.created_by_user_id = creator_id  # Different user is creator
        mock_expense_repo.get_by_id = AsyncMock(return_value=mock_expense)

        with pytest.raises(
            AuthorizationError, match="Only the expense creator can delete it"
        ):
            await ExpenseService.delete_expense(expense_id, test_user_id, mock_db)
