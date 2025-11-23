"""Pytest fixtures and configuration"""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.user import User

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://expense_user:expense_pass@localhost:5432/expense_share_test"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,  # No connection pooling for tests
    echo=False,
)

# Create test session factory
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database session for each test.
    Rolls back all changes after the test completes.
    """
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user"""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """Create a second test user"""
    user = User(
        id=uuid4(),
        username="testuser2",
        email="test2@example.com",
        full_name="Test User 2",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user3(db_session: AsyncSession) -> User:
    """Create a third test user"""
    user = User(
        id=uuid4(),
        username="testuser3",
        email="test3@example.com",
        full_name="Test User 3",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, test_user: User) -> str:
    """Get authentication token for test user"""
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    """Get authentication headers"""
    return {"Authorization": f"Bearer {auth_token}"}
