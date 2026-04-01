"""
Base repository with generic workspace-scoped CRUD operations.
All domain repositories inherit from this.
"""

from typing import Any
from database import get_db


class BaseRepository:
    """Generic CRUD with workspace scoping."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.db = get_db()

    def _query(self):
        return self.db.table(self.table_name)

    # ── Read ──

    def find_all(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        desc: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        q = self._query().select("*")
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        q = q.order(order_by, desc=desc)
        if limit:
            q = q.limit(limit)
        if offset:
            q = q.range(offset, offset + (limit or 20) - 1)
        return q.execute().data or []

    def find_by_id(self, record_id: str) -> dict | None:
        result = self._query().select("*").eq("id", record_id).maybe_single().execute()
        return result.data

    def count(self, filters: dict[str, Any] | None = None) -> int:
        q = self._query().select("id", count="exact")
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        result = q.execute()
        return result.count or 0

    # ── Write ──

    def create(self, data: dict) -> dict:
        result = self._query().insert(data).execute()
        return result.data[0]

    def update(self, record_id: str, data: dict) -> dict | None:
        clean = {k: v for k, v in data.items() if v is not None}
        if not clean:
            return self.find_by_id(record_id)
        result = self._query().update(clean).eq("id", record_id).execute()
        return result.data[0] if result.data else None

    def delete(self, record_id: str) -> bool:
        self._query().delete().eq("id", record_id).execute()
        return True

    # ── Workspace-scoped helpers ──

    def find_all_in_workspace(
        self,
        workspace_id: str,
        extra_filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        desc: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        filters = {"workspace_id": workspace_id}
        if extra_filters:
            filters.update(extra_filters)
        return self.find_all(filters=filters, order_by=order_by, desc=desc, limit=limit, offset=offset)

    def count_in_workspace(self, workspace_id: str, extra_filters: dict[str, Any] | None = None) -> int:
        filters = {"workspace_id": workspace_id}
        if extra_filters:
            filters.update(extra_filters)
        return self.count(filters=filters)
