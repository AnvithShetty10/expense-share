"""Test split calculations"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.models.expense import SplitType
from app.services.split_strategies import (
    EqualSplitStrategy,
    ManualSplitStrategy,
    PercentageSplitStrategy,
    get_split_strategy,
)


class TestGetSplitStrategy:
    """Test get_split_strategy factory function"""

    def test_get_equal_strategy(self):
        """Test getting equal split strategy"""
        strategy = get_split_strategy(SplitType.EQUAL)
        assert isinstance(strategy, EqualSplitStrategy)

    def test_get_percentage_strategy(self):
        """Test getting percentage split strategy"""
        strategy = get_split_strategy(SplitType.PERCENTAGE)
        assert isinstance(strategy, PercentageSplitStrategy)

    def test_get_manual_strategy(self):
        """Test getting manual split strategy"""
        strategy = get_split_strategy(SplitType.MANUAL)
        assert isinstance(strategy, ManualSplitStrategy)


class TestEqualSplitStrategy:
    """Test equal split strategy"""

    @pytest.fixture
    def strategy(self):
        return EqualSplitStrategy()

    def test_equal_split_two_participants(self, strategy):
        """Test equal split with 2 participants"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": None},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": None},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 2
        assert splits[0].amount_owed == Decimal("50.00")
        assert splits[1].amount_owed == Decimal("50.00")
        assert sum(s.amount_owed for s in splits) == total_amount

    def test_equal_split_three_participants(self, strategy):
        """Test equal split with 3 participants (requires rounding)"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": None},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": None},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": None},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 3
        # 100 / 3 = 33.33... each
        # With rounding adjustment: 33.33, 33.33, 33.34
        assert splits[0].amount_owed == Decimal("33.33")
        assert splits[1].amount_owed == Decimal("33.33")
        assert splits[2].amount_owed == Decimal("33.34")
        assert sum(s.amount_owed for s in splits) == total_amount

    def test_equal_split_single_participant(self, strategy):
        """Test equal split with 1 participant"""
        total_amount = Decimal("50.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("50"), "amount_owed": None},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 1
        assert splits[0].amount_owed == Decimal("50.00")

    def test_equal_split_zero_participants(self, strategy):
        """Test equal split with no participants returns empty list"""
        total_amount = Decimal("100.00")
        participants = []

        # Implementation returns empty list instead of raising error
        splits = strategy.calculate_splits(total_amount, participants)
        assert splits == []

    def test_equal_split_large_amount(self, strategy):
        """Test equal split with large amount"""
        total_amount = Decimal("999999.99")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("999999.99"), "amount_owed": None},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": None},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 2
        # Should round to 2 decimal places
        assert sum(s.amount_owed for s in splits) == total_amount


class TestPercentageSplitStrategy:
    """Test percentage split strategy"""

    @pytest.fixture
    def strategy(self):
        return PercentageSplitStrategy()

    def test_percentage_split_valid(self, strategy):
        """Test percentage split with valid percentages"""
        total_amount = Decimal("1000.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("1000"), "percentage": Decimal("60")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "percentage": Decimal("40")},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 2
        assert splits[0].amount_owed == Decimal("600.00")
        assert splits[1].amount_owed == Decimal("400.00")
        assert sum(s.amount_owed for s in splits) == total_amount

    def test_percentage_split_with_rounding(self, strategy):
        """Test percentage split with rounding"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "percentage": Decimal("33.33")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "percentage": Decimal("33.33")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "percentage": Decimal("33.34")},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 3
        # Should adjust for rounding to ensure sum equals total
        assert sum(s.amount_owed for s in splits) == total_amount

    def test_percentage_split_missing_percentage(self, strategy):
        """Test percentage split with missing percentage raises error (defaults to 0, sum won't be 100)"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "percentage": None},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "percentage": Decimal("50")},
        ]

        # Missing percentage defaults to 0, so sum will be 50% not 100%
        with pytest.raises(ValidationError, match="Percentages must sum to 100"):
            strategy.calculate_splits(total_amount, participants)

    def test_percentage_split_invalid_total(self, strategy):
        """Test percentage split with invalid total raises error"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "percentage": Decimal("50")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "percentage": Decimal("40")},
        ]

        with pytest.raises(ValidationError, match="Percentages must sum to 100"):
            strategy.calculate_splits(total_amount, participants)

    def test_percentage_split_negative_percentage(self, strategy):
        """Test percentage split with negative percentage raises error"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "percentage": Decimal("-10")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "percentage": Decimal("110")},
        ]

        with pytest.raises(ValidationError, match="Percentage must be between 0 and 100"):
            strategy.calculate_splits(total_amount, participants)

    def test_percentage_split_over_100_percent(self, strategy):
        """Test percentage split with single percentage > 100 raises error"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "percentage": Decimal("101")},
        ]

        # Will first fail the sum check (101 != 100)
        with pytest.raises(ValidationError, match="Percentages must sum to 100"):
            strategy.calculate_splits(total_amount, participants)

    def test_percentage_split_100_percent_single(self, strategy):
        """Test percentage split with single participant at 100%"""
        total_amount = Decimal("500.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("500"), "percentage": Decimal("100")},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 1
        assert splits[0].amount_owed == Decimal("500.00")


class TestManualSplitStrategy:
    """Test manual split strategy"""

    @pytest.fixture
    def strategy(self):
        return ManualSplitStrategy()

    def test_manual_split_valid(self, strategy):
        """Test manual split with valid amounts"""
        total_amount = Decimal("150.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": Decimal("50")},
            {"user_id": uuid4(), "amount_paid": Decimal("50"), "amount_owed": Decimal("70")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": Decimal("30")},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 3
        assert splits[0].amount_owed == Decimal("50.00")
        assert splits[1].amount_owed == Decimal("70.00")
        assert splits[2].amount_owed == Decimal("30.00")
        assert sum(s.amount_owed for s in splits) == total_amount

    def test_manual_split_missing_amount_owed(self, strategy):
        """Test manual split with missing amount_owed (defaults to 0, sum won't match)"""
        total_amount = Decimal("101.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": None},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": Decimal("100")},
        ]

        # Missing amount_owed defaults to 0, so sum will be 100 not matching expected split
        with pytest.raises(ValidationError, match="Sum of manual amounts.*must equal total amount"):
            strategy.calculate_splits(total_amount, participants)

    def test_manual_split_negative_amount(self, strategy):
        """Test manual split with negative amount raises error"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": Decimal("-10")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": Decimal("110")},
        ]

        with pytest.raises(ValidationError, match="Amount owed cannot be negative"):
            strategy.calculate_splits(total_amount, participants)

    def test_manual_split_with_rounding_adjustment(self, strategy):
        """Test manual split allows small rounding differences (0.01)"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": Decimal("33.33")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": Decimal("33.33")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": Decimal("33.33")},
        ]

        # Sum is 99.99, difference of 0.01 is within tolerance
        splits = strategy.calculate_splits(total_amount, participants)
        assert len(splits) == 3
        # Implementation allows 0.01 difference, doesn't auto-adjust
        assert sum(s.amount_owed for s in splits) == Decimal("99.99")
        assert splits[2].amount_owed == Decimal("33.33")

    def test_manual_split_zero_amount_owed(self, strategy):
        """Test manual split allows zero amount_owed"""
        total_amount = Decimal("100.00")
        participants = [
            {"user_id": uuid4(), "amount_paid": Decimal("100"), "amount_owed": Decimal("100")},
            {"user_id": uuid4(), "amount_paid": Decimal("0"), "amount_owed": Decimal("0")},
        ]

        splits = strategy.calculate_splits(total_amount, participants)

        assert len(splits) == 2
        assert splits[0].amount_owed == Decimal("100.00")
        assert splits[1].amount_owed == Decimal("0.00")
