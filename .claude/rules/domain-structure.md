# Domain Structure Standard

## Adding a new domain (checklist)

```
1. shared/models/{name}.py          ← ORM model
2. alembic/env.py                   ← add import
3. python migrate.py generate "add {name} table"
4. Review alembic/versions/<rev>_add_{name}_table.py
5. python migrate.py                ← apply + seed
6. domains/{name}/
   ├── __init__.py
   ├── schemas.py                   ← Pydantic in/out
   ├── repository.py                ← DB queries only
   ├── service.py                   ← business logic
   └── router.py                   ← FastAPI routes
7. domains/__init__.py              ← include_router
```

## Model rules (shared/models/)

```python
class MyTable(Base):
    __tablename__ = "my_tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Rules:
- UUID PKs, `gen_random_uuid()` or `default=uuid.uuid4`
- All workspace-scoped tables: `workspace_id` FK + `ON DELETE CASCADE` + `index=True`
- Timestamps: `server_default=func.now()`, `TIMESTAMPTZ`
- Enums: `VARCHAR(N)` + `CHECK` constraint — never Postgres ENUM type
- Flexible data: `JSONB` not multiple nullable columns

## Repository rules (domains/{name}/repository.py)

```python
from shared.base_repository import BaseRepository
from shared.models.my_model import MyModel

class MyRepository(BaseRepository):
    model = MyModel

    async def find_by_project(self, project_id: str) -> list[MyModel]:
        stmt = select(self.model).where(
            self.model.project_id == project_id
        ).order_by(self.model.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

Rules:
- Inherit `BaseRepository` from `shared.base_repository` (not domain copy)
- Repositories: DB queries only — no HTTP, no business logic
- Methods: `find_*` for reads, inherited `create/update/delete`
- Never raise `HTTPException` — that's the service/router layer

## Migration rules (alembic/versions/)

```python
# Filename: <short_description>.py
# Always idempotent — safe to run on both fresh and existing DBs

def upgrade():
    op.execute("""
        ALTER TABLE my_tables
            ADD COLUMN IF NOT EXISTS new_col VARCHAR(100)
    """)
    op.create_index(
        "ix_my_tables_new_col", "my_tables", ["new_col"],
        if_not_exists=True   # requires alembic 1.13+, else use op.execute
    )

def downgrade():
    op.execute("ALTER TABLE my_tables DROP COLUMN IF EXISTS new_col")
```

Rules:
- Always use `IF NOT EXISTS` / `IF EXISTS` — migrations must be idempotent
- Always add indexes for FK columns and columns used in WHERE clauses
- Always write `downgrade()` that fully reverses the upgrade
- Never delete a migration that has been applied to any environment
- Never edit an existing migration — add a new one instead

## Migration workflow

```bash
# Detect drift between models and DB (no changes applied)
python migrate.py check

# Create a new migration from model diff
python migrate.py generate "add sprint cycles table"

# Apply all pending migrations
python migrate.py

# Roll back one step
python migrate.py downgrade -1

# See what's applied
python migrate.py current
python migrate.py history
```

## Availability & fault tolerance patterns

**Docker**: Use `migrate` init service — workspace never starts if migrations fail:
```yaml
workspace:
  depends_on:
    migrate:
      condition: service_completed_successfully
  environment:
    - SKIP_MIGRATIONS=true   # migration is the migrate service's job
```

**Health checks**: Every service exposes `/health` — gateway uses it for routing.

**DB pool**: `NullPool` for migrations (short-lived); asyncpg pool for app (long-lived).

**Idempotency**: All seed data uses `ON CONFLICT DO NOTHING`.

**Graceful shutdown**: `lifespan` context manager closes DB + Redis connections cleanly.
