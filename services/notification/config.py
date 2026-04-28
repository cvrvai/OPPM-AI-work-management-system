"""Notification service configuration."""

from functools import lru_cache
from shared.config import SharedSettings


class NotificationSettings(SharedSettings):
    debug: bool = True
    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> NotificationSettings:
    return NotificationSettings()
