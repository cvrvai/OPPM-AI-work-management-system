"""MCP service settings."""

from shared.config import SharedSettings


class MCPSettings(SharedSettings):
    """MCP-specific settings."""
    pass

_settings: MCPSettings | None = None


def get_settings() -> MCPSettings:
    global _settings
    if _settings is None:
        _settings = MCPSettings()
    return _settings
