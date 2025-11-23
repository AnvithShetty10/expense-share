"""User schemas"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import PaginationMeta


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user"""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating user information"""

    full_name: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response (no password)"""

    id: UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserBase):
    """Schema for user in database (with hashed password)"""

    id: UUID
    hashed_password: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Response schema for user list"""

    items: List[UserResponse]
    pagination: PaginationMeta
