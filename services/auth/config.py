"""Auth service configuration."""

from functools import lru_cache
from shared.config import SharedSettings


class AuthSettings(SharedSettings):
    # Email (Resend) — for password reset flows
    resend_api_key: str = ""
    app_url: str = "http://localhost:5173"
    email_from: str = "OPPM <noreply@oppm.dev>"

    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> AuthSettings:
    return AuthSettings()
