"""Notification schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class NotificationCreate(BaseModel):
    type: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    message: str = ""
    link: Optional[str] = None
    metadata: Optional[dict] = None
