#!/usr/bin/env bash
# Start the full production stack (Docker Compose).
# Usage: ./deploy/scripts/start.sh [--build]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

BUILD_FLAG=""
if [[ "${1:-}" == "--build" ]]; then
    BUILD_FLAG="--build"
fi

echo "[start] Starting OPPM production stack..."
docker compose -f deploy/docker/compose.prod.yml up -d $BUILD_FLAG
echo "[start] Stack is up. Gateway available at http://localhost:80"
echo "[start] Prometheus: http://localhost:9090"
echo "[start] Grafana:    http://localhost:3000"
