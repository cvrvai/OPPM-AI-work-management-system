"""Base repository for AI service."""

from shared.database import get_db


class BaseRepository:
    """Thin wrapper around Supabase table operations."""

    def __init__(self, table_name: str):
        self.table_name = table_name

    def _query(self):
        return get_db().table(self.table_name)

    def find_by_id(self, record_id: str) -> dict | None:
        result = self._query().select("*").eq("id", record_id).limit(1).execute()
        return result.data[0] if result.data else None

    def find_all(
        self,
        filters: dict | None = None,
        order_by: str = "created_at",
        desc: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        q = self._query().select("*")
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        q = q.order(order_by, desc=desc).range(offset, offset + limit - 1)
        return q.execute().data or []

    def create(self, data: dict) -> dict:
        result = self._query().insert(data).execute()
        return result.data[0]

    def update(self, record_id: str, data: dict) -> dict | None:
        result = self._query().update(data).eq("id", record_id).execute()
        return result.data[0] if result.data else None

    def delete(self, record_id: str) -> bool:
        self._query().delete().eq("id", record_id).execute()
        return True
