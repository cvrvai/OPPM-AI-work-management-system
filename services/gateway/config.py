"""
Gateway service configuration.

Service URLs support comma-separated values for round-robin load balancing.
Example: WORKSPACE_URLS=http://localhost:8000,http://localhost:8010
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class GatewaySettings(BaseSettings):
    # Backend service instance URLs (comma-separated for load balancing)
    workspace_urls:     str = "http://127.0.0.1:8000"
    intelligence_urls:  str = "http://127.0.0.1:8001"
    integrations_urls:  str = "http://127.0.0.1:8002"
    automation_urls:   str = "http://127.0.0.1:8003"

    # Legacy aliases for backward compatibility
    core_urls: str = ""  # fallback to workspace_urls if empty
    ai_urls:   str = ""  # fallback to intelligence_urls if empty
    git_urls:  str = ""  # fallback to integrations_urls if empty
    mcp_urls:  str = ""  # fallback to automation_urls if empty

    # Gateway port
    port: int = 8080

    # CORS origins (comma-separated)
    cors_origins: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}

    def resolved_workspace_urls(self) -> str:
        return self.core_urls or self.workspace_urls

    def resolved_intelligence_urls(self) -> str:
        return self.ai_urls or self.intelligence_urls

    def resolved_integrations_urls(self) -> str:
        return self.git_urls or self.integrations_urls

    def resolved_automation_urls(self) -> str:
        return self.mcp_urls or self.automation_urls


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
