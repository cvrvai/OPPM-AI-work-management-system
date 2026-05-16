"""
Standalone database migration runner.

Usage:
  python migrate.py                       # apply all pending migrations + seed
  python migrate.py upgrade [target]      # apply migrations (default: heads)
  python migrate.py downgrade -1          # roll back one step
  python migrate.py current               # show current revision
  python migrate.py history               # show migration history
  python migrate.py check                 # detect model/DB drift (no changes applied)
  python migrate.py generate "msg"        # autogenerate new migration from model diff
  python migrate.py seed                  # seed required bootstrap data

Environment:
  DATABASE_URL  — PostgreSQL async connection string (required)
  SUPABASE_BRIDGE_WORKSPACE_ID — if set, workspace is seeded automatically

Docker one-shot:
  docker run --rm --network oppm-network \
    -e DATABASE_URL=postgresql+asyncpg://... \
    workmanagement-backend-workspace:latest \
    python migrate.py

Workflow for adding a new table:
  1. Add model class to shared/models/{name}.py
  2. Import it in alembic/env.py
  3. Run: python migrate.py generate "add {name} table"
  4. Review the generated file in alembic/versions/
  5. Run: python migrate.py
"""

import asyncio
import logging
import os
import sys
import uuid

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("migrate")


def _get_alembic_cfg() -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini")
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        # Alembic uses sync driver; convert asyncpg → psycopg2 for the CLI
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def run_upgrade(target: str = "heads") -> None:
    logger.info("Running migrations → %s", target)
    cfg = _get_alembic_cfg()
    alembic_command.upgrade(cfg, target)
    logger.info("Migrations complete")


def run_downgrade(target: str) -> None:
    logger.info("Rolling back → %s", target)
    cfg = _get_alembic_cfg()
    alembic_command.downgrade(cfg, target)
    logger.info("Rollback complete")


def run_current() -> None:
    cfg = _get_alembic_cfg()
    alembic_command.current(cfg)


def run_history() -> None:
    cfg = _get_alembic_cfg()
    alembic_command.history(cfg)


def run_check() -> None:
    """Detect model/DB drift without applying anything. Exits non-zero if drift found."""
    logger.info("Checking for model/DB drift...")
    cfg = _get_alembic_cfg()
    alembic_command.check(cfg)
    logger.info("Schema is in sync — no pending migrations detected")


def run_generate(message: str) -> None:
    """Autogenerate a new migration from the current model diff."""
    if not message:
        logger.error("generate requires a description: python migrate.py generate 'add my table'")
        sys.exit(1)
    logger.info("Generating migration: %s", message)
    cfg = _get_alembic_cfg()
    alembic_command.revision(cfg, message=message, autogenerate=True)
    logger.info("Migration file created — review it in alembic/versions/ before applying")


async def _seed_bridge_workspace() -> None:
    """Ensure the Supabase bridge workspace exists in the DB."""
    workspace_id = os.environ.get("SUPABASE_BRIDGE_WORKSPACE_ID", "")
    if not workspace_id:
        logger.info("SUPABASE_BRIDGE_WORKSPACE_ID not set — skipping workspace seed")
        return

    # Use sync psycopg2 for seeding (simpler here than full async setup)
    import psycopg2

    db_url = os.environ.get("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "").replace("postgresql+psycopg2://", "")
    # parse: user:pass@host:port/dbname
    conn = psycopg2.connect(f"postgresql://{sync_url}")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO workspaces (id, name, slug, description, plan, settings, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            workspace_id,
            "One Utilities Bridge",
            "one-utilities-bridge",
            "Auto-provisioned bridge workspace for Supabase auth pass-through",
            "pro",
            "{}",  # empty JSONB settings
            str(uuid.uuid4()),
        ),
    )
    rows = cur.rowcount
    cur.close()
    conn.close()

    if rows:
        logger.info("Seeded bridge workspace %s", workspace_id)
    else:
        logger.info("Bridge workspace %s already exists", workspace_id)


def run_seed() -> None:
    asyncio.run(_seed_bridge_workspace())


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "upgrade":
        target = args[1] if len(args) > 1 else "heads"
        run_upgrade(target)
        run_seed()

    elif args[0] == "downgrade":
        target = args[1] if len(args) > 1 else "-1"
        run_downgrade(target)

    elif args[0] == "current":
        run_current()

    elif args[0] == "history":
        run_history()

    elif args[0] == "check":
        run_check()

    elif args[0] == "generate":
        message = " ".join(args[1:])
        run_generate(message)

    elif args[0] == "seed":
        run_seed()

    else:
        print(__doc__)
        sys.exit(1)
