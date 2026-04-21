"""
Memory loader — loads recent interaction history from audit_log for context enrichment.

Provides conversation memory by reading past AI chat interactions.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.notification import AuditLog

logger = logging.getLogger(__name__)

MAX_MEMORY_CHARS = 4000


async def load_memory(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    limit: int = 20,
    project_id: str | None = None,
) -> str:
    """Load recent AI interaction history for the user in this workspace.

    When project_id is provided, only returns interactions from that project.
    Returns a formatted string of recent user–AI exchanges from the audit log.
    """
    try:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.workspace_id == workspace_id,
                AuditLog.user_id == user_id,
                AuditLog.action == "ai_chat",
            )
        )
        if project_id:
            stmt = stmt.where(
                AuditLog.new_data["project_id"].astext == project_id
            )
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        entries = list(result.scalars().all())
    except Exception as e:
        logger.warning("Failed to load memory from audit_log: %s", e)
        return ""

    if not entries:
        return ""

    # Reverse to chronological order
    entries.reverse()

    lines = ["## Conversation Memory (recent interactions)"]
    total_chars = 0

    for entry in entries:
        data = entry.new_data or {}
        user_msg = data.get("user_message", "")
        ai_resp = data.get("ai_response", "")
        timestamp = str(entry.created_at)[:16] if entry.created_at else ""

        if not user_msg:
            continue

        line = f"[{timestamp}] User: {user_msg}\nAI: {ai_resp}\n"
        if total_chars + len(line) > MAX_MEMORY_CHARS:
            break

        lines.append(line)
        total_chars += len(line)

    return "\n".join(lines) if len(lines) > 1 else ""
