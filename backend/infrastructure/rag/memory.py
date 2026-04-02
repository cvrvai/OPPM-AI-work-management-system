"""
Memory loader — loads recent interaction history from audit_log for context enrichment.

Provides conversation memory by reading past AI chat interactions.
"""

import logging

from database import get_db

logger = logging.getLogger(__name__)

MAX_MEMORY_CHARS = 4000


async def load_memory(
    workspace_id: str,
    user_id: str,
    limit: int = 20,
) -> str:
    """Load recent AI interaction history for the user in this workspace.

    Returns a formatted string of recent user–AI exchanges from the audit log.
    """
    db = get_db()

    try:
        result = (
            db.table("audit_log")
            .select("action, new_data, created_at")
            .eq("workspace_id", workspace_id)
            .eq("user_id", user_id)
            .eq("action", "ai_chat")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to load memory from audit_log: %s", e)
        return ""

    entries = result.data or []
    if not entries:
        return ""

    # Reverse to chronological order
    entries.reverse()

    lines = ["## Conversation Memory (recent interactions)"]
    total_chars = 0

    for entry in entries:
        data = entry.get("new_data") or {}
        user_msg = data.get("user_message", "")
        ai_resp = data.get("ai_response", "")
        timestamp = entry.get("created_at", "")[:16]  # YYYY-MM-DDTHH:MM

        if not user_msg:
            continue

        line = f"[{timestamp}] User: {user_msg}\nAI: {ai_resp}\n"
        if total_chars + len(line) > MAX_MEMORY_CHARS:
            break

        lines.append(line)
        total_chars += len(line)

    return "\n".join(lines) if len(lines) > 1 else ""
