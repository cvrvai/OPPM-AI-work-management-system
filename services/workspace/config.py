"""
Workspace service configuration — extends shared settings with workspace-specific vars.
"""

from functools import lru_cache
from shared.config import SharedSettings


class WorkspaceSettings(SharedSettings):
    """Settings for the workspace service."""

    # Email (Resend)
    resend_api_key: str = ""
    app_url: str = "http://localhost:5173"
    email_from: str = "OPPM <noreply@oppm.dev>"

    # Embedding (for document_indexer)
    openai_api_key: str = ""

    # Google Sheets MVP (service account)
    google_service_account_json: str = ""
    google_service_account_file: str = ""

    # App
    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> WorkspaceSettings:
    return WorkspaceSettings()
