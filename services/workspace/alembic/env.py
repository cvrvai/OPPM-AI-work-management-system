import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make shared/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Import ALL models so autogenerate detects every table change.
# When you add a new model file, add its import here too.
from shared.database import Base
import shared.models.user
import shared.models.workspace
import shared.models.project
import shared.models.project_file
import shared.models.task
import shared.models.oppm
import shared.models.git
import shared.models.ai_model
import shared.models.notification
import shared.models.embedding
import shared.models.agile
import shared.models.waterfall
import shared.models.workspace_ai_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment if DATABASE_URL is set
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    # alembic needs psycopg2-style URL (no +asyncpg)
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

