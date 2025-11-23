"""Configuration management"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # Application
    app_name: str = "Expense Share"
    debug: bool = False
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # Database
    database_url: str

    # JWT Authentication
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    allowed_origins: List[str] = []

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is at least 32 characters"""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL starts with postgresql"""
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
