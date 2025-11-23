"""Auth schemas (token, login)"""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseModel):
    """Token payload data"""
    user_id: Optional[UUID] = None


class LoginRequest(BaseModel):
    """Login request schema"""
    username: str = Field(..., description="Email or username")
    password: str
