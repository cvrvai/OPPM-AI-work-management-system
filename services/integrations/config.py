"""Integrations service configuration."""

from shared.config import SharedSettings


class IntegrationsSettings(SharedSettings):
    """Integrations-service-specific settings."""
    # Intelligence service URL for commit analysis
    intelligence_service_url: str = "http://intelligence:8001"

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings = None


def get_settings() -> IntegrationsSettings:
    global _settings
    if _settings is None:
        _settings = IntegrationsSettings()
    return _settings
