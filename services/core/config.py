"""
Core service configuration — extends shared settings with core-specific vars.
"""

from functools import lru_cache
from shared.config import SharedSettings


class CoreSettings(SharedSettings):
    """Settings for the core service."""

    # JWT (legacy, not used by backend directly)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"

    # Email (Resend)
    resend_api_key: str = ""
    app_url: str = "http://localhost:5173"
    email_from: str = "OPPM <noreply@oppm.dev>"

    # Embedding (for document_indexer)
    openai_api_key: str = ""

    # App
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> CoreSettings:
    return CoreSettings()
