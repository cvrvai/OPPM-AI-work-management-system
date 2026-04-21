"""Git service configuration."""

from shared.config import SharedSettings


class GitSettings(SharedSettings):
    """Git-service-specific settings."""
    # AI service URL for commit analysis
    ai_service_url: str = "http://ai:8001"

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings = None


def get_settings() -> GitSettings:
    global _settings
    if _settings is None:
        _settings = GitSettings()
    return _settings
