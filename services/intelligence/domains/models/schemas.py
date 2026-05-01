"""AI model schemas."""

from pydantic import BaseModel
from typing import Optional


class AIModelConfig(BaseModel):
    model_config = {"protected_namespaces": ()}

    name: str
    provider: str
    model_id: str
    endpoint_url: Optional[str] = None
    is_active: bool = True
