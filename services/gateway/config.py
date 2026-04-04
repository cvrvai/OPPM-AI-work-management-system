"""
Gateway service configuration.

Service URLs support comma-separated values for round-robin load balancing.
Example: CORE_URLS=http://localhost:8000,http://localhost:8010
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class GatewaySettings(BaseSettings):
    # Backend service instance URLs (comma-separated for load balancing)
    core_urls: str = "http://127.0.0.1:8000"
    ai_urls:   str = "http://127.0.0.1:8001"
    git_urls:  str = "http://127.0.0.1:8002"
    mcp_urls:  str = "http://127.0.0.1:8003"

    # Gateway port
    port: int = 8080

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
