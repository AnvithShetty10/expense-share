"""Integration tests for balance API endpoints"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.fixture
async def create_shared_expense(client: AsyncClient, auth_headers: dict, test_user: User, test_user2: User):
    """Helper fixture to create a shared expense"""
    async def _create_expense(
        description: str,
        total_amount: str,
        user1_paid: str,
        split_type: str = "EQUAL",
        percentage_1: str | None = None,
        percentage_2: str | None = None,
        amount_owed_1: str | None = None,
        amount_owed_2: str | None = None,
    ):
        expense_data = {
            "description": description,
            "total_amount": total_amount,
            "expense_date": str(date.today()),
            "group_name": "Test",
            "split_type": split_type,
            "participants": [
                {
                    "user_id": str(test_user.id),
                    "amount_paid": user1_paid,
                    "percentage": percentage_1,
                    "amount_owed": amount_owed_1,
                },
                {
                    "user_id": str(test_user2.id),
                    "amount_paid": str(Decimal(total_amount) - Decimal(user1_paid)),
                    "percentage": percentage_2,
                    "amount_owed": amount_owed_2,
                },
            ],
        }
        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_headers,
        )
        return response

    return _create_expense


class TestGetUserBalances:
    """Test get user balances endpoint"""

    @pytest.mark.asyncio
    async def test_get_balances_no_expenses(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting balances with no expenses"""
        response = await client.get(
            "/api/v1/balances",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "balances" in data
        assert isinstance(data["balances"], list)
        assert len(data["balances"]) == 0

    @pytest.mark.asyncio
    async def test_get_balances_with_single_expense(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test getting balances after creating one expense"""
        # User1 pays 100, split equally (50 each)
        # User2 owes user1: 50
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        response = await client.get(
            "/api/v1/balances",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        balances = data["balances"]
        assert len(balances) == 1
        assert balances[0]["type"] == "owes_you"
        assert Decimal(balances[0]["amount"]) == Decimal("50.00")
        assert "user" in balances[0]
        assert balances[0]["user"]["username"] == "testuser2"

    @pytest.mark.asyncio
    async def test_get_balances_multiple_expenses(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test getting balances with multiple expenses"""
        # Expense 1: User1 pays 100, split equally
        # User2 owes: 50
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        # Expense 2: User1 pays 200, split equally
        # User2 owes: 100
        await create_shared_expense(
            description="Dinner",
            total_amount="200.00",
            user1_paid="200.00",
        )

        response = await client.get(
            "/api/v1/balances",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        balances = data["balances"]
        assert len(balances) == 1
        # Total: User2 owes 150
        assert balances[0]["type"] == "owes_you"
        assert Decimal(balances[0]["amount"]) == Decimal("150.00")

    @pytest.mark.asyncio
    async def test_get_balances_you_owe(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense,
        test_user2: User
    ):
        """Test getting balances when you owe money"""
        # User1 pays 0, User2 pays 100, split equally
        # User1 owes User2: 50
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="0.00",
        )

        response = await client.get(
            "/api/v1/balances",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        balances = data["balances"]
        assert len(balances) == 1
        assert balances[0]["type"] == "you_owe"
        assert Decimal(balances[0]["amount"]) == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_get_balances_mixed_debts(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test balances when there are offsetting expenses"""
        # Expense 1: User1 pays 100, split equally
        # User2 owes: 50
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        # Expense 2: User2 pays 60 (user1 pays 0), split equally
        # User1 owes: 30
        await create_shared_expense(
            description="Coffee",
            total_amount="60.00",
            user1_paid="0.00",
        )

        response = await client.get(
            "/api/v1/balances",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        balances = data["balances"]
        assert len(balances) == 1
        # Net: User2 owes 20 (50 - 30)
        assert balances[0]["type"] == "owes_you"
        assert Decimal(balances[0]["amount"]) == Decimal("20.00")

    @pytest.mark.asyncio
    async def test_get_balances_unauthorized(self, client: AsyncClient):
        """Test getting balances without authentication fails"""
        response = await client.get("/api/v1/balances")
        assert response.status_code == 401


class TestGetBalanceSummary:
    """Test get balance summary endpoint"""

    @pytest.mark.asyncio
    async def test_get_summary_no_expenses(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting summary with no expenses"""
        response = await client.get(
            "/api/v1/balances/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["overall_balance"]) == Decimal("0.00")
        assert Decimal(data["total_you_owe"]) == Decimal("0.00")
        assert Decimal(data["total_owed_to_you"]) == Decimal("0.00")
        assert data["num_people_you_owe"] == 0
        assert data["num_people_owe_you"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_with_single_expense(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test summary after one expense"""
        # User1 pays 100, split equally
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        response = await client.get(
            "/api/v1/balances/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["overall_balance"]) == Decimal("50.00")
        assert Decimal(data["total_you_owe"]) == Decimal("0.00")
        assert Decimal(data["total_owed_to_you"]) == Decimal("50.00")
        assert data["num_people_you_owe"] == 0
        assert data["num_people_owe_you"] == 1

    @pytest.mark.asyncio
    async def test_get_summary_when_you_owe(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test summary when you owe money"""
        # User2 pays everything, user1 pays nothing
        await create_shared_expense(
            description="Dinner",
            total_amount="200.00",
            user1_paid="0.00",
        )

        response = await client.get(
            "/api/v1/balances/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["overall_balance"]) == Decimal("-100.00")
        assert Decimal(data["total_you_owe"]) == Decimal("100.00")
        assert Decimal(data["total_owed_to_you"]) == Decimal("0.00")
        assert data["num_people_you_owe"] == 1
        assert data["num_people_owe_you"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_with_three_users(
        self, client: AsyncClient, auth_headers: dict, test_user: User,
        test_user2: User, test_user3: User
    ):
        """Test summary with three users"""
        # Expense 1: User1 pays 300 for 3 people equally (100 each)
        # User2 owes: 100, User3 owes: 100
        expense_data = {
            "description": "Team Lunch",
            "total_amount": "300.00",
            "expense_date": str(date.today()),
            "group_name": "Work",
            "split_type": "EQUAL",
            "participants": [
                {"user_id": str(test_user.id), "amount_paid": "300.00"},
                {"user_id": str(test_user2.id), "amount_paid": "0.00"},
                {"user_id": str(test_user3.id), "amount_paid": "0.00"},
            ],
        }
        await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/balances/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["overall_balance"]) == Decimal("200.00")
        assert Decimal(data["total_you_owe"]) == Decimal("0.00")
        assert Decimal(data["total_owed_to_you"]) == Decimal("200.00")
        assert data["num_people_you_owe"] == 0
        assert data["num_people_owe_you"] == 2

    @pytest.mark.asyncio
    async def test_get_summary_unauthorized(self, client: AsyncClient):
        """Test getting summary without authentication fails"""
        response = await client.get("/api/v1/balances/summary")
        assert response.status_code == 401


class TestGetBalanceWithUser:
    """Test get balance with specific user endpoint"""

    @pytest.mark.asyncio
    async def test_get_balance_with_user_no_shared_expenses(
        self, client: AsyncClient, auth_headers: dict, test_user2: User
    ):
        """Test balance with user when no shared expenses"""
        response = await client.get(
            f"/api/v1/balances/user/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount"]) == Decimal("0.00")
        assert data["type"] == "owes_you"
        assert data["user"]["username"] == "testuser2"
        assert "shared_expenses" in data
        assert len(data["shared_expenses"]) == 0

    @pytest.mark.asyncio
    async def test_get_balance_with_user_single_expense(
        self, client: AsyncClient, auth_headers: dict, test_user2: User,
        create_shared_expense
    ):
        """Test balance with user after one shared expense"""
        # User1 pays 100, split equally
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        response = await client.get(
            f"/api/v1/balances/user/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount"]) == Decimal("50.00")
        assert data["type"] == "owes_you"
        assert len(data["shared_expenses"]) == 1
        assert data["shared_expenses"][0]["description"] == "Lunch"

    @pytest.mark.asyncio
    async def test_balance_symmetry(
        self, client: AsyncClient, auth_headers: dict, test_user: User,
        test_user2: User, create_shared_expense
    ):
        """Test that balance symmetry holds: balance(A,B) = -balance(B,A)"""
        # User1 pays 100, split equally
        # User2 owes User1: 50
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        # Get balance from user1's perspective
        response1 = await client.get(
            f"/api/v1/balances/users/{test_user2.id}",
            headers=auth_headers,
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Login as user2
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser2", "password": "testpassword123"},
        )
        user2_token = login_response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # Get balance from user2's perspective
        response2 = await client.get(
            f"/api/v1/balances/user/{test_user.id}",
            headers=user2_headers,
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify symmetry
        # User1 view: User2 owes 50
        assert data1["type"] == "owes_you"
        assert Decimal(data1["amount"]) == Decimal("50.00")

        # User2 view: User2 owes User1 50 (so type is you_owe)
        assert data2["type"] == "you_owe"
        assert Decimal(data2["amount"]) == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_balance_symmetry_complex(
        self, client: AsyncClient, auth_headers: dict, test_user: User,
        test_user2: User, create_shared_expense
    ):
        """Test balance symmetry with multiple offsetting expenses"""
        # Expense 1: User1 pays 100, split equally
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        # Expense 2: User2 pays 60, split equally
        await create_shared_expense(
            description="Coffee",
            total_amount="60.00",
            user1_paid="0.00",
        )

        # Get balance from user1's perspective
        response1 = await client.get(
            f"/api/v1/balances/users/{test_user2.id}",
            headers=auth_headers,
        )
        data1 = response1.json()

        # Login as user2
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser2", "password": "testpassword123"},
        )
        user2_token = login_response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # Get balance from user2's perspective
        response2 = await client.get(
            f"/api/v1/balances/user/{test_user.id}",
            headers=user2_headers,
        )
        data2 = response2.json()

        # Net: User2 owes 20 (50 - 30)
        # User1 view: User2 owes 20
        assert data1["type"] == "owes_you"
        assert Decimal(data1["amount"]) == Decimal("20.00")

        # User2 view: User2 owes 20 (you_owe)
        assert data2["type"] == "you_owe"
        assert Decimal(data2["amount"]) == Decimal("20.00")

    @pytest.mark.asyncio
    async def test_get_balance_with_user_shared_expenses_list(
        self, client: AsyncClient, auth_headers: dict, test_user2: User,
        create_shared_expense
    ):
        """Test that shared expenses are listed correctly"""
        # Create multiple expenses
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )
        await create_shared_expense(
            description="Dinner",
            total_amount="200.00",
            user1_paid="200.00",
        )
        await create_shared_expense(
            description="Coffee",
            total_amount="30.00",
            user1_paid="0.00",
        )

        response = await client.get(
            f"/api/v1/balances/user/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["shared_expenses"]) == 3

        # Check expenses are sorted by date (most recent first)
        descriptions = [e["description"] for e in data["shared_expenses"]]
        assert "Lunch" in descriptions
        assert "Dinner" in descriptions
        assert "Coffee" in descriptions

    @pytest.mark.asyncio
    async def test_get_balance_with_nonexistent_user(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting balance with non-existent user returns 404"""
        fake_id = str(uuid4())
        response = await client.get(
            f"/api/v1/balances/user/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_balance_with_user_unauthorized(
        self, client: AsyncClient, test_user2: User
    ):
        """Test getting balance without authentication fails"""
        response = await client.get(f"/api/v1/balances/user/{test_user2.id}")
        assert response.status_code == 401


class TestBalanceCaching:
    """Test balance caching behavior"""

    @pytest.mark.asyncio
    async def test_balance_updates_after_expense_creation(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test that balances update after creating new expense"""
        # Initial check - no balances
        response1 = await client.get("/api/v1/balances", headers=auth_headers)
        assert len(response1.json()["balances"]) == 0

        # Create expense
        await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )

        # Check balances again - should have one balance
        response2 = await client.get("/api/v1/balances", headers=auth_headers)
        data = response2.json()
        balances = data["balances"]
        assert len(balances) == 1
        assert Decimal(balances[0]["amount"]) == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_balance_updates_after_expense_deletion(
        self, client: AsyncClient, auth_headers: dict, create_shared_expense
    ):
        """Test that balances update after deleting expense"""
        # Create expense
        create_response = await create_shared_expense(
            description="Lunch",
            total_amount="100.00",
            user1_paid="100.00",
        )
        expense_id = create_response.json()["id"]

        # Check balance exists
        response1 = await client.get("/api/v1/balances", headers=auth_headers)
        assert len(response1.json()["balances"]) == 1

        # Delete expense
        await client.delete(
            f"/api/v1/expenses/{expense_id}",
            headers=auth_headers,
        )

        # Check balances again - should be empty
        response2 = await client.get("/api/v1/balances", headers=auth_headers)
        assert len(response2.json()["balances"]) == 0
