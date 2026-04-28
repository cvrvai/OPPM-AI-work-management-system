"""Workspace service configuration."""

from functools import lru_cache
from shared.config import SharedSettings


class WorkspaceSettings(SharedSettings):
    debug: bool = True
    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> WorkspaceSettings:
    return WorkspaceSettings()
