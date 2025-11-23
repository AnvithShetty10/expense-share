"""Unit tests for balance calculations"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.expense import Expense
from app.models.expense_participant import ExpenseParticipant
from app.services.balance_service import BalanceService


@pytest.fixture
def user1_id():
    """First user ID"""
    return uuid4()


@pytest.fixture
def user2_id():
    """Second user ID"""
    return uuid4()


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock()


class TestSerializeDeserializeBalances:
    """Test balance serialization and deserialization"""

    def test_serialize_balances(self, user1_id, user2_id):
        """Test serializing balances to JSON"""
        balances = {
            user1_id: Decimal("50.00"),
            user2_id: Decimal("30.50"),
        }

        result = BalanceService._serialize_balances(balances)

        # Should be valid JSON string
        assert isinstance(result, str)
        assert str(user1_id) in result
        assert "50.00" in result

    def test_deserialize_balances(self, user1_id, user2_id):
        """Test deserializing balances from JSON"""
        json_str = f'{{"{user1_id}": "50.00", "{user2_id}": "30.50"}}'

        result = BalanceService._deserialize_balances(json_str)

        assert isinstance(result, dict)
        assert user1_id in result
        assert result[user1_id] == Decimal("50.00")
        assert result[user2_id] == Decimal("30.50")

    def test_serialize_deserialize_round_trip(self, user1_id, user2_id):
        """Test that serialize and deserialize are inverse operations"""
        original = {
            user1_id: Decimal("100.00"),
            user2_id: Decimal("0.00"),
        }

        serialized = BalanceService._serialize_balances(original)
        deserialized = BalanceService._deserialize_balances(serialized)

        assert deserialized == original


class TestCalculatePairwiseBalance:
    """Test pairwise balance calculation"""

    @pytest.mark.asyncio
    @patch("app.services.balance_service.ExpenseRepository")
    async def test_pairwise_balance_simple(
        self, mock_expense_repo, mock_db, user1_id, user2_id
    ):
        """Test simple pairwise balance calculation"""
        # User1 paid 100, owes 50; User2 paid 0, owes 50
        # User2 owes User1: 50
        participant1 = MagicMock()
        participant1.user_id = user1_id
        participant1.amount_paid = Decimal("100.00")
        participant1.amount_owed = Decimal("50.00")

        participant2 = MagicMock()
        participant2.user_id = user2_id
        participant2.amount_paid = Decimal("0.00")
        participant2.amount_owed = Decimal("50.00")

        expense = MagicMock()
        expense.participants = [participant1, participant2]

        mock_expense_repo.get_user_expenses = AsyncMock(return_value=[expense])

        result = await BalanceService._calculate_pairwise_balance(
            user1_id, user2_id, mock_db
        )

        # User2 owes User1 50
        assert result == Decimal("50.00")

    @pytest.mark.asyncio
    @patch("app.services.balance_service.ExpenseRepository")
    async def test_pairwise_balance_symmetry(
        self, mock_expense_repo, mock_db, user1_id, user2_id
    ):
        """Test that pairwise balance is symmetric"""
        # Setup expense
        participant1 = MagicMock()
        participant1.user_id = user1_id
        participant1.amount_paid = Decimal("100.00")
        participant1.amount_owed = Decimal("50.00")

        participant2 = MagicMock()
        participant2.user_id = user2_id
        participant2.amount_paid = Decimal("0.00")
        participant2.amount_owed = Decimal("50.00")

        expense = MagicMock()
        expense.participants = [participant1, participant2]

        # Mock return for both calls (must return awaitable)
        mock_expense_repo.get_user_expenses = AsyncMock(return_value=[expense])

        balance_1_to_2 = await BalanceService._calculate_pairwise_balance(
            user1_id, user2_id, mock_db
        )

        balance_2_to_1 = await BalanceService._calculate_pairwise_balance(
            user2_id, user1_id, mock_db
        )

        # Should be negatives of each other
        assert balance_1_to_2 == -balance_2_to_1

    @pytest.mark.asyncio
    @patch("app.services.balance_service.ExpenseRepository")
    async def test_pairwise_balance_no_shared_expenses(
        self, mock_expense_repo, mock_db, user1_id, user2_id
    ):
        """Test pairwise balance with no shared expenses"""
        mock_expense_repo.get_user_expenses = AsyncMock(return_value=[])

        result = await BalanceService._calculate_pairwise_balance(
            user1_id, user2_id, mock_db
        )

        assert result == Decimal("0.00")

    @pytest.mark.asyncio
    @patch("app.services.balance_service.ExpenseRepository")
    async def test_pairwise_balance_multiple_expenses(
        self, mock_expense_repo, mock_db, user1_id, user2_id
    ):
        """Test pairwise balance with multiple expenses"""
        # Expense 1: User1 paid 100, both owe 50
        p1_exp1 = MagicMock()
        p1_exp1.user_id = user1_id
        p1_exp1.amount_paid = Decimal("100.00")
        p1_exp1.amount_owed = Decimal("50.00")

        p2_exp1 = MagicMock()
        p2_exp1.user_id = user2_id
        p2_exp1.amount_paid = Decimal("0.00")
        p2_exp1.amount_owed = Decimal("50.00")

        expense1 = MagicMock()
        expense1.participants = [p1_exp1, p2_exp1]

        # Expense 2: User2 paid 60, both owe 30
        p1_exp2 = MagicMock()
        p1_exp2.user_id = user1_id
        p1_exp2.amount_paid = Decimal("0.00")
        p1_exp2.amount_owed = Decimal("30.00")

        p2_exp2 = MagicMock()
        p2_exp2.user_id = user2_id
        p2_exp2.amount_paid = Decimal("60.00")
        p2_exp2.amount_owed = Decimal("30.00")

        expense2 = MagicMock()
        expense2.participants = [p1_exp2, p2_exp2]

        mock_expense_repo.get_user_expenses = AsyncMock(return_value=[expense1, expense2])

        result = await BalanceService._calculate_pairwise_balance(
            user1_id, user2_id, mock_db
        )

        # User2 owes User1: 50 (from exp1) - 30 (from exp2) = 20
        assert result == Decimal("20.00")


class TestGetUserBalances:
    """Test getting all user balances"""

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService._calculate_user_balances")
    @patch("app.services.balance_service.UserRepository")
    @patch("app.services.balance_service.CacheService")
    async def test_get_user_balances_with_cache_hit(
        self, mock_cache, mock_user_repo, mock_calculate, mock_db, user1_id, user2_id
    ):
        """Test getting balances with cache hit"""
        # Setup cached data
        cached_balances = {user2_id: Decimal("50.00")}
        cached_json = BalanceService._serialize_balances(cached_balances)
        mock_cache.get = AsyncMock(return_value=cached_json)

        # Setup user (must return awaitable and have real values for Pydantic)
        from app.models.user import User
        from datetime import datetime
        mock_user = User(
            id=user2_id,
            username="user2",
            email="user2@example.com",
            full_name="User Two",
            hashed_password="hashed",
            is_active=True,
            created_at=datetime.now()
        )
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        result = await BalanceService.get_user_balances(user1_id, mock_db, use_cache=True)

        # Should use cache
        mock_cache.get.assert_called_once()
        mock_calculate.assert_not_called()

        # Should return list of balances
        assert len(result) == 1
        assert result[0].amount == Decimal("50.00")
        assert result[0].type == "owes_you"

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService._calculate_user_balances")
    @patch("app.services.balance_service.UserRepository")
    @patch("app.services.balance_service.CacheService")
    async def test_get_user_balances_with_cache_miss(
        self, mock_cache, mock_user_repo, mock_calculate, mock_db, user1_id, user2_id
    ):
        """Test getting balances with cache miss"""
        # Setup cache miss
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        # Setup calculation result
        mock_calculate = AsyncMock(return_value={user2_id: Decimal("50.00")})

        # Setup user (must return awaitable and have real values for Pydantic)
        from app.models.user import User
        from datetime import datetime
        mock_user = User(
            id=user2_id,
            username="user2",
            email="user2@example.com",
            full_name="User Two",
            hashed_password="hashed",
            is_active=True,
            created_at=datetime.now()
        )
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        # Need to patch _calculate_user_balances
        with patch.object(BalanceService, '_calculate_user_balances', mock_calculate):
            result = await BalanceService.get_user_balances(user1_id, mock_db, use_cache=True)

        # Should calculate and cache
        mock_calculate.assert_called_once()
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService._calculate_user_balances")
    @patch("app.services.balance_service.UserRepository")
    async def test_get_user_balances_without_cache(
        self, mock_user_repo, mock_calculate, mock_db, user1_id, user2_id
    ):
        """Test getting balances without using cache"""
        # Setup calculation result
        mock_calculate = AsyncMock(return_value={user2_id: Decimal("30.00")})

        # Setup user (must return awaitable and have real values for Pydantic)
        from app.models.user import User
        from datetime import datetime
        mock_user = User(
            id=user2_id,
            username="user2",
            email="user2@example.com",
            full_name="User Two",
            hashed_password="hashed",
            is_active=True,
            created_at=datetime.now()
        )
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        # Need to patch _calculate_user_balances
        with patch.object(BalanceService, '_calculate_user_balances', mock_calculate):
            result = await BalanceService.get_user_balances(
                user1_id, mock_db, use_cache=False
            )

        # Should always calculate
        mock_calculate.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService._calculate_user_balances")
    @patch("app.services.balance_service.UserRepository")
    async def test_get_user_balances_you_owe(
        self, mock_user_repo, mock_calculate, mock_db, user1_id, user2_id
    ):
        """Test balances when user owes money"""
        # Negative balance means user owes
        mock_calculate = AsyncMock(return_value={user2_id: Decimal("-30.00")})

        # Setup user (must return awaitable and have real values for Pydantic)
        from app.models.user import User
        from datetime import datetime
        mock_user = User(
            id=user2_id,
            username="user2",
            email="user2@example.com",
            full_name="User Two",
            hashed_password="hashed",
            is_active=True,
            created_at=datetime.now()
        )
        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        # Need to patch _calculate_user_balances
        with patch.object(BalanceService, '_calculate_user_balances', mock_calculate):
            result = await BalanceService.get_user_balances(
                user1_id, mock_db, use_cache=False
            )

        assert len(result) == 1
        assert result[0].type == "you_owe"
        assert result[0].amount == Decimal("30.00")  # Should be positive


class TestGetBalanceSummary:
    """Test balance summary"""

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService.get_user_balances")
    async def test_get_balance_summary_owes_you(
        self, mock_get_balances, mock_db, user1_id
    ):
        """Test summary when people owe you"""
        # Mock balances
        balance1 = MagicMock()
        balance1.type = "owes_you"
        balance1.amount = Decimal("50.00")

        balance2 = MagicMock()
        balance2.type = "owes_you"
        balance2.amount = Decimal("30.00")

        mock_get_balances.return_value = [balance1, balance2]

        result = await BalanceService.get_balance_summary(user1_id, mock_db)

        assert result.overall_balance == Decimal("80.00")
        assert result.total_owed_to_you == Decimal("80.00")
        assert result.total_you_owe == Decimal("0.00")
        assert result.num_people_owe_you == 2
        assert result.num_people_you_owe == 0

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService.get_user_balances")
    async def test_get_balance_summary_you_owe(
        self, mock_get_balances, mock_db, user1_id
    ):
        """Test summary when you owe people"""
        # Mock balances
        balance1 = MagicMock()
        balance1.type = "you_owe"
        balance1.amount = Decimal("40.00")

        mock_get_balances.return_value = [balance1]

        result = await BalanceService.get_balance_summary(user1_id, mock_db)

        assert result.overall_balance == Decimal("-40.00")
        assert result.total_owed_to_you == Decimal("0.00")
        assert result.total_you_owe == Decimal("40.00")
        assert result.num_people_owe_you == 0
        assert result.num_people_you_owe == 1

    @pytest.mark.asyncio
    @patch("app.services.balance_service.BalanceService.get_user_balances")
    async def test_get_balance_summary_mixed(
        self, mock_get_balances, mock_db, user1_id
    ):
        """Test summary with mixed balances"""
        # Mock balances
        balance1 = MagicMock()
        balance1.type = "owes_you"
        balance1.amount = Decimal("100.00")

        balance2 = MagicMock()
        balance2.type = "you_owe"
        balance2.amount = Decimal("30.00")

        mock_get_balances.return_value = [balance1, balance2]

        result = await BalanceService.get_balance_summary(user1_id, mock_db)

        assert result.overall_balance == Decimal("70.00")
        assert result.total_owed_to_you == Decimal("100.00")
        assert result.total_you_owe == Decimal("30.00")
        assert result.num_people_owe_you == 1
        assert result.num_people_you_owe == 1


class TestInvalidateBalances:
    """Test cache invalidation"""

    @pytest.mark.asyncio
    @patch("app.services.balance_service.CacheService")
    async def test_invalidate_balances_for_users(self, mock_cache, user1_id, user2_id):
        """Test invalidating balances for multiple users"""
        mock_cache.delete_multiple = AsyncMock(return_value=True)

        user_ids = [user1_id, user2_id]
        result = await BalanceService.invalidate_balances_for_users(user_ids)

        assert result is True
        mock_cache.delete_multiple.assert_called_once()

        # Check the cache keys
        call_args = mock_cache.delete_multiple.call_args[0][0]
        assert f"balance:{user1_id}" in call_args
        assert f"balance:{user2_id}" in call_args

    @pytest.mark.asyncio
    async def test_invalidate_balances_empty_list(self):
        """Test invalidating with empty user list"""
        result = await BalanceService.invalidate_balances_for_users([])
        assert result is True
