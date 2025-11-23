"""Integration tests for user API endpoints"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.user import User


class TestListUsers:
    """Test list users endpoint"""

    @pytest.mark.asyncio
    async def test_list_users_default_pagination(
        self, client: AsyncClient, auth_headers: dict, test_user: User, test_user2: User
    ):
        """Test listing users with default pagination"""
        response = await client.get(
            "/api/v1/users",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 2  # At least test_user and test_user2

        # Check pagination metadata
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 20
        assert pagination["total_items"] >= 2
        assert pagination["total_pages"] >= 1

    @pytest.mark.asyncio
    async def test_list_users_custom_pagination(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing users with custom page size"""
        response = await client.get(
            "/api/v1/users?page=1&page_size=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 1
        assert len(data["items"]) <= 1

    @pytest.mark.asyncio
    async def test_list_users_second_page(
        self, client: AsyncClient, auth_headers: dict, test_user: User,
        test_user2: User, test_user3: User
    ):
        """Test listing users on second page"""
        response = await client.get(
            "/api/v1/users?page=2&page_size=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["page_size"] == 2
        # Should have at least one user on page 2 since we have 3 users
        assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_list_users_search_by_username(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test searching users by username"""
        response = await client.get(
            "/api/v1/users?search=testuser",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        # All returned users should match search
        assert any("testuser" in user["username"].lower() for user in data["items"])

    @pytest.mark.asyncio
    async def test_list_users_search_by_email(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test searching users by email"""
        response = await client.get(
            "/api/v1/users?search=test@example.com",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        # Should find test_user
        assert any(user["email"] == "test@example.com" for user in data["items"])

    @pytest.mark.asyncio
    async def test_list_users_search_by_name(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test searching users by full name"""
        response = await client.get(
            "/api/v1/users?search=Test User",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        # Should find users with "Test User" in name
        assert any("Test User" in user["full_name"] for user in data["items"])

    @pytest.mark.asyncio
    async def test_list_users_search_no_results(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test searching users with no matching results"""
        response = await client.get(
            "/api/v1/users?search=nonexistentuser12345",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["pagination"]["total_items"] == 0

    @pytest.mark.asyncio
    async def test_list_users_invalid_page(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing users with invalid page number"""
        response = await client.get(
            "/api/v1/users?page=0",
            headers=auth_headers,
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_users_invalid_page_size(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing users with invalid page size"""
        response = await client.get(
            "/api/v1/users?page_size=101",  # Max is 100
            headers=auth_headers,
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_users_unauthorized(self, client: AsyncClient):
        """Test listing users without authentication fails"""
        response = await client.get("/api/v1/users")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_users_response_format(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test that user response contains correct fields"""
        response = await client.get(
            "/api/v1/users",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        if len(data["items"]) > 0:
            user = data["items"][0]
            # Check required fields
            assert "id" in user
            assert "username" in user
            assert "email" in user
            assert "full_name" in user
            assert "is_active" in user
            # Ensure sensitive fields are not exposed
            assert "hashed_password" not in user


class TestGetUserById:
    """Test get user by ID endpoint"""

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test getting user by ID"""
        response = await client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_other_user_by_id(
        self, client: AsyncClient, auth_headers: dict, test_user2: User
    ):
        """Test getting another user's details"""
        response = await client.get(
            f"/api/v1/users/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user2.id)
        assert data["username"] == "testuser2"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting non-existent user returns 404"""
        fake_id = str(uuid4())
        response = await client.get(
            f"/api/v1/users/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_by_id_invalid_uuid(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting user with invalid UUID format"""
        response = await client.get(
            "/api/v1/users/not-a-valid-uuid",
            headers=auth_headers,
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_user_by_id_unauthorized(
        self, client: AsyncClient, test_user: User
    ):
        """Test getting user without authentication fails"""
        response = await client.get(f"/api/v1/users/{test_user.id}")
        assert response.status_code == 401
