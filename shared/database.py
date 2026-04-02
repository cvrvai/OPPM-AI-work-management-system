"""
Supabase client singleton shared across all microservices.
Uses service_role_key (bypasses RLS) with fallback to anon_key.
"""

import logging
from supabase import create_client, Client
from shared.config import get_settings

logger = logging.getLogger(__name__)

_client: Client | None = None
_PLACEHOLDER = "your-service-role-key-here"


def get_db() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        key = settings.supabase_service_role_key
        if not key or key == _PLACEHOLDER:
            logger.warning(
                "SUPABASE_SERVICE_ROLE_KEY not set — falling back to anon key. "
                "Set the real service role key in .env for full access."
            )
            key = settings.supabase_anon_key
        _client = create_client(settings.supabase_url, key)
    return _client
