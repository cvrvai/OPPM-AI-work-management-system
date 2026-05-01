"""Automation service settings."""

from shared.config import SharedSettings


class AutomationSettings(SharedSettings):
    """Automation-specific settings."""
    pass

_settings: MCPSettings | None = None


def get_settings() -> AutomationSettings:
    global _settings
    if _settings is None:
        _settings = AutomationSettings()
    return _settings
