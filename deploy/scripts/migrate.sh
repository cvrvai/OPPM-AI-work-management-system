#!/usr/bin/env bash
# Run Alembic migrations against the shared database.
# Usage: ./deploy/scripts/migrate.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[migrate] Loading environment from services/.env"
set -a
# shellcheck source=/dev/null
source services/.env
set +a

# Convert asyncpg URL to psycopg2 for alembic
export DATABASE_URL="${DATABASE_URL/postgresql+asyncpg/postgresql}"

echo "[migrate] Running: alembic -c migrations/alembic.ini upgrade head"
alembic -c migrations/alembic.ini upgrade head
echo "[migrate] Done."
