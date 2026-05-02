"""WorkspaceAiConfig repository — per-workspace AI configuration key-value store."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.workspace_ai_config import WorkspaceAiConfig


class WorkspaceAiConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, workspace_id: str, config_key: str) -> WorkspaceAiConfig | None:
        stmt = (
            select(WorkspaceAiConfig)
            .where(
                WorkspaceAiConfig.workspace_id == workspace_id,
                WorkspaceAiConfig.config_key == config_key,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, workspace_id: str, config_key: str, config_value: str) -> WorkspaceAiConfig:
        stmt = (
            insert(WorkspaceAiConfig)
            .values(
                workspace_id=workspace_id,
                config_key=config_key,
                config_value=config_value,
            )
            .on_conflict_do_update(
                constraint="uq_workspace_ai_config_ws_key",
                set_={
                    "config_value": config_value,
                    "updated_at": WorkspaceAiConfig.updated_at,
                },
            )
            .returning(WorkspaceAiConfig)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one()

    async def delete(self, workspace_id: str, config_key: str) -> bool:
        row = await self.get(workspace_id, config_key)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True
