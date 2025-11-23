"""Integration tests for expense API endpoints"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.fixture
async def sample_expense_data(test_user: User, test_user2: User):
    """Sample expense data for testing"""
    return {
        "description": "Team Lunch",
        "total_amount": "300.00",
        "expense_date": str(date.today()),
        "group_name": "Work",
        "split_type": "EQUAL",
        "participants": [
            {
                "user_id": str(test_user.id),
                "amount_paid": "300.00",
                "amount_owed": None,
                "percentage": None,
            },
            {
                "user_id": str(test_user2.id),
                "amount_paid": "0.00",
                "amount_owed": None,
                "percentage": None,
            },
        ],
    }


class TestCreateExpense:
    """Test expense creation endpoint"""

    @pytest.mark.asyncio
    async def test_create_expense_equal_split(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict
    ):
        """Test creating expense with equal split"""
        response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "Team Lunch"
        assert Decimal(data["total_amount"]) == Decimal("300.00")
        assert data["split_type"] == "EQUAL"
        assert len(data["participants"]) == 2
        # Each participant should owe 150 (300/2)
        assert all(Decimal(p["amount_owed"]) == Decimal("150.00") for p in data["participants"])

    @pytest.mark.asyncio
    async def test_create_expense_percentage_split(
        self, client: AsyncClient, auth_headers: dict, test_user: User, test_user2: User
    ):
        """Test creating expense with percentage split"""
        expense_data = {
            "description": "Dinner",
            "total_amount": "200.00",
            "expense_date": str(date.today()),
            "split_type": "PERCENTAGE",
            "participants": [
                {
                    "user_id": str(test_user.id),
                    "amount_paid": "200.00",
                    "percentage": "60.00",
                },
                {
                    "user_id": str(test_user2.id),
                    "amount_paid": "0.00",
                    "percentage": "40.00",
                },
            ],
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        # User1: 60% of 200 = 120, User2: 40% of 200 = 80
        participants = sorted(data["participants"], key=lambda p: Decimal(p["amount_owed"]))
        assert Decimal(participants[0]["amount_owed"]) == Decimal("80.00")
        assert Decimal(participants[1]["amount_owed"]) == Decimal("120.00")

    @pytest.mark.asyncio
    async def test_create_expense_manual_split(
        self, client: AsyncClient, auth_headers: dict, test_user: User, test_user2: User
    ):
        """Test creating expense with manual split"""
        expense_data = {
            "description": "Groceries",
            "total_amount": "150.00",
            "expense_date": str(date.today()),
            "split_type": "MANUAL",
            "participants": [
                {
                    "user_id": str(test_user.id),
                    "amount_paid": "150.00",
                    "amount_owed": "100.00",
                },
                {
                    "user_id": str(test_user2.id),
                    "amount_paid": "0.00",
                    "amount_owed": "50.00",
                },
            ],
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        participants = sorted(data["participants"], key=lambda p: Decimal(p["amount_owed"]))
        assert Decimal(participants[0]["amount_owed"]) == Decimal("50.00")
        assert Decimal(participants[1]["amount_owed"]) == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_create_expense_unauthorized(
        self, client: AsyncClient, sample_expense_data: dict
    ):
        """Test creating expense without authentication fails"""
        response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_expense_invalid_total(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test creating expense with mismatched total fails"""
        expense_data = {
            "description": "Invalid",
            "total_amount": "100.00",
            "expense_date": str(date.today()),
            "split_type": "EQUAL",
            "participants": [
                {
                    "user_id": str(test_user.id),
                    "amount_paid": "50.00",  # Doesn't match total
                },
            ],
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_headers,
        )

        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_expense_with_idempotency_key(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict
    ):
        """Test idempotency key prevents duplicate expense creation"""
        idempotency_key = str(uuid4())
        headers = {**auth_headers, "Idempotency-Key": idempotency_key}

        # First request
        response1 = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=headers,
        )
        assert response1.status_code == 201
        expense_id_1 = response1.json()["id"]

        # Second request with same key should return same expense
        response2 = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=headers,
        )
        assert response2.status_code == 201
        expense_id_2 = response2.json()["id"]
        assert expense_id_1 == expense_id_2


class TestListExpenses:
    """Test list expenses endpoint"""

    @pytest.mark.asyncio
    async def test_list_expenses(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict
    ):
        """Test listing user's expenses"""
        # Create an expense first
        await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )

        # List expenses
        response = await client.get(
            "/api/v1/expenses",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) >= 1
        assert data["pagination"]["total_items"] >= 1

    @pytest.mark.asyncio
    async def test_list_expenses_with_pagination(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test expense list pagination"""
        response = await client.get(
            "/api/v1/expenses?page=1&page_size=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_expenses_unauthorized(self, client: AsyncClient):
        """Test listing expenses without auth fails"""
        response = await client.get("/api/v1/expenses")
        assert response.status_code == 401


class TestGetExpenseDetail:
    """Test get expense detail endpoint"""

    @pytest.mark.asyncio
    async def test_get_expense_detail(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict
    ):
        """Test getting expense details"""
        # Create expense
        create_response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )
        expense_id = create_response.json()["id"]

        # Get expense details
        response = await client.get(
            f"/api/v1/expenses/{expense_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == expense_id
        assert data["description"] == "Team Lunch"
        assert len(data["participants"]) == 2

    @pytest.mark.asyncio
    async def test_get_expense_detail_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting non-existent expense returns 404"""
        fake_id = str(uuid4())
        response = await client.get(
            f"/api/v1/expenses/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_expense_detail_unauthorized(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict,
        test_user3: User
    ):
        """Test getting expense you're not part of fails"""
        # Create expense as test_user
        create_response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )
        expense_id = create_response.json()["id"]

        # Try to get as test_user3 (not a participant)
        # First login as test_user3
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser3", "password": "testpassword123"},
        )
        user3_token = login_response.json()["access_token"]
        user3_headers = {"Authorization": f"Bearer {user3_token}"}

        response = await client.get(
            f"/api/v1/expenses/{expense_id}",
            headers=user3_headers,
        )

        assert response.status_code == 403


class TestUpdateExpense:
    """Test update expense endpoint"""

    @pytest.mark.asyncio
    async def test_update_expense(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict,
        test_user: User, test_user2: User
    ):
        """Test updating expense"""
        # Create expense
        create_response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )
        expense_id = create_response.json()["id"]

        # Update expense
        updated_data = {
            "description": "Updated Lunch",
            "total_amount": "400.00",
            "expense_date": str(date.today()),
            "split_type": "EQUAL",
            "participants": [
                {
                    "user_id": str(test_user.id),
                    "amount_paid": "400.00",
                },
                {
                    "user_id": str(test_user2.id),
                    "amount_paid": "0.00",
                },
            ],
        }

        response = await client.put(
            f"/api/v1/expenses/{expense_id}",
            json=updated_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated Lunch"
        assert Decimal(data["total_amount"]) == Decimal("400.00")

    @pytest.mark.asyncio
    async def test_update_expense_not_creator(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict,
        test_user2: User
    ):
        """Test non-creator cannot update expense"""
        # Create expense as test_user
        create_response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )
        expense_id = create_response.json()["id"]

        # Try to update as test_user2
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser2", "password": "testpassword123"},
        )
        user2_token = login_response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        response = await client.put(
            f"/api/v1/expenses/{expense_id}",
            json=sample_expense_data,
            headers=user2_headers,
        )

        assert response.status_code == 403


class TestDeleteExpense:
    """Test delete expense endpoint"""

    @pytest.mark.asyncio
    async def test_delete_expense(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict
    ):
        """Test deleting expense"""
        # Create expense
        create_response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )
        expense_id = create_response.json()["id"]

        # Delete expense
        response = await client.delete(
            f"/api/v1/expenses/{expense_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(
            f"/api/v1/expenses/{expense_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_expense_not_creator(
        self, client: AsyncClient, auth_headers: dict, sample_expense_data: dict
    ):
        """Test non-creator cannot delete expense"""
        # Create expense as test_user
        create_response = await client.post(
            "/api/v1/expenses",
            json=sample_expense_data,
            headers=auth_headers,
        )
        expense_id = create_response.json()["id"]

        # Try to delete as test_user2
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser2", "password": "testpassword123"},
        )
        user2_token = login_response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        response = await client.delete(
            f"/api/v1/expenses/{expense_id}",
            headers=user2_headers,
        )

        assert response.status_code == 403
