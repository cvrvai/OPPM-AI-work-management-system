"""
Base configuration shared across all OPPM microservices.
Each service extends this with its own settings via subclass.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class SharedSettings(BaseSettings):
    """Base settings needed by the shared auth/database layer."""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Environment
    environment: str = "development"

    # Service-to-service auth
    internal_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> SharedSettings:
    return SharedSettings()
