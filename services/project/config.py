"""Project service configuration."""

from functools import lru_cache
from shared.config import SharedSettings


class ProjectSettings(SharedSettings):
    debug: bool = True
    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> ProjectSettings:
    return ProjectSettings()
