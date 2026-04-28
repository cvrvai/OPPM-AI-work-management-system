"""
Base configuration shared across all OPPM microservices.
Each service extends this with its own settings via subclass.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class SharedSettings(BaseSettings):
    """Base settings needed by the shared auth/database layer."""

    # Database
    database_url: str = "postgresql+asyncpg://oppm:oppm_dev_password@localhost:5432/oppm"

    # Redis
    redis_url: str = "redis://:oppm_dev_password@localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Environment
    environment: str = "development"

    # Service-to-service auth
    internal_api_key: str = ""

    # CORS
    cors_origins: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> SharedSettings:
    return SharedSettings()
