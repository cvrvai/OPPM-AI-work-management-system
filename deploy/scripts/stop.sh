#!/usr/bin/env bash
# Stop and remove all containers.
# Usage: ./deploy/scripts/stop.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[stop] Stopping OPPM production stack..."
docker compose -f deploy/docker/compose.prod.yml down
echo "[stop] Done."
