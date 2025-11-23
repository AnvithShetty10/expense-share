"""Integration tests for auth API endpoints"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestRegisterEndpoint:
    """Test user registration endpoint"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful user registration"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert "id" in data
        assert "hashed_password" not in data
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_register_duplicate_username(
        self, client: AsyncClient, test_user: User
    ):
        """Test registration with duplicate username fails"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",  # Already exists
                "email": "different@example.com",
                "password": "SecurePass123!",
                "full_name": "Another User",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email fails"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "differentuser",
                "email": "test@example.com",  # Already exists
                "password": "SecurePass123!",
                "full_name": "Another User",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email format"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "not-an-email",
                "password": "SecurePass123!",
                "full_name": "New User",
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with short password fails"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "short",
                "full_name": "New User",
            },
        )

        assert response.status_code == 422
        assert "at least 8 characters" in str(response.json()).lower()


class TestLoginEndpoint:
    """Test user login endpoint"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "testpassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password fails"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user fails"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_missing_credentials(self, client: AsyncClient):
        """Test login without credentials fails"""
        response = await client.post("/api/v1/auth/login", data={})

        assert response.status_code == 422  # Validation error


class TestGetCurrentUserEndpoint:
    """Test get current user endpoint"""

    @pytest.mark.asyncio
    async def test_get_current_user_success(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test getting current user with valid token"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert data["id"] == str(test_user.id)
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without token fails"""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token fails"""
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_header(self, client: AsyncClient):
        """Test getting current user with malformed auth header fails"""
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "NotBearer token"}
        )

        assert response.status_code == 401
