# Docker Compose — OPPM AI Work Management System

Complete reference for running the OPPM stack in Docker.

---

## Quick Start

### Development (hot-reload)
```powershell
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up --build
```

### Production (built images, no volume mounts)
```powershell
docker compose -f docker-compose.microservices.yml up --build
```

---

## Compose File Overview

| File | Purpose |
|---|---|
| `docker-compose.yml` | Infrastructure only — postgres + redis with exposed ports |
| `docker-compose.microservices.yml` | All services — full stack including gateway, microservices, frontend |
| `docker-compose.dev.yml` | Dev overrides — hot-reload commands, source volume mounts, direct port exposure |

Compose files are layered. Settings in a later `-f` file override the earlier one.

---

## Service Map

| Service | Container Port | Host Port (dev) | Image / Build |
|---|---|---|---|
| postgres | 5432 | 5432 | `pgvector/pgvector:pg16` |
| redis | 6379 | 6379 | `redis:7-alpine` |
| gateway | 80 | 80 | `./gateway` (nginx:1.27-alpine) |
| core | 8000 | 8000 | `services/core/Dockerfile` |
| ai | 8001 | 8001 | `services/ai/Dockerfile` |
| git | 8002 | 8002 | `services/git/Dockerfile` |
| mcp | 8003 | 8003 | `services/mcp/Dockerfile` |
| frontend | 5173 | 5173 | `frontend/Dockerfile` |

In production mode all microservice ports are `expose`-only (internal Docker network). Only port 80 (gateway) is published to the host.

---

## Startup Order

```
postgres (healthcheck: pg_isready)
    └── core, ai, git, mcp  (healthcheck: HTTP /health)
redis
    └── core
            └── gateway (waits for core + ai + git + mcp healthy)
```

The gateway only starts after all four microservices pass their health checks.

---

## Dockerfiles

All Python service Dockerfiles follow the same pattern:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared      # installs shared package deps
COPY services/<name>/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/                            # enables "from shared.xxx import ..."
COPY services/<name>/ .
EXPOSE <port>
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "<port>"]
```

The `shared/` directory is installed as an editable package at `/shared` and resolved via `PYTHONPATH=/` so all services can `import shared`.

The frontend Dockerfile:

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

---

## nginx Gateway Routing

The gateway (`gateway/nginx.conf`) routes all traffic on port 80:

| Path pattern | Upstream |
|---|---|
| `/api/v1/workspaces/*/projects/*/ai/` | ai:8001 |
| `/api/v1/workspaces/*/rag/` | ai:8001 |
| `/api/v1/workspaces/*/ai/` | ai:8001 |
| `/internal/analyze-commits` | ai:8001 |
| `/api/v1/workspaces/*/mcp/` | mcp:8003 |
| `/api/v1/workspaces/*/github-accounts` | git:8002 |
| `/api/v1/workspaces/*/commits` | git:8002 |
| `/api/v1/workspaces/*/git/` | git:8002 |
| `POST /api/v1/git/webhook` | git:8002 |
| `/mcp` (SSE) | mcp:8003 |
| `/health/core`, `/health/ai`, etc. | respective service /health |
| `/api/` (all others) | core:8000 |
| `/` (fallback) | frontend:5173 |

CORS is handled globally on the gateway for `localhost` origins. The Docker DNS resolver (`127.0.0.11`) is queried on every request (TTL 5s) to avoid stale IPs when containers restart.

---

## Environment Variables

All microservices load `services/.env` via `env_file`. Copy `services/.env.example` to `services/.env` and fill in values before running.

Variables injected by `docker-compose.microservices.yml` (override `.env`):

| Service | Variable | Value |
|---|---|---|
| core | `DATABASE_URL` | `postgresql+asyncpg://oppm:<DB_PASSWORD>@postgres:5432/oppm` |
| core | `REDIS_URL` | `redis://:<REDIS_PASSWORD>@redis:6379/0` |
| ai | `DATABASE_URL` | same pattern |
| git | `DATABASE_URL` | same pattern |
| git | `AI_SERVICE_URL` | `http://ai:8001` |
| mcp | `DATABASE_URL` | same pattern |

Passwords default to `oppm_dev_password` if the env var is not set.

---

## Dev Mode Details (`docker-compose.dev.yml`)

The dev override does three things for each Python service:

1. **Volume mounts** — mounts live source into the container so code changes are reflected immediately without rebuilding
2. **Hot-reload command** — overrides CMD to `uvicorn ... --reload`
3. **Direct port exposure** — publishes all service ports to the host

| Service | Source mount | Container path |
|---|---|---|
| core | `./shared` | `/shared` |
| core | `./services/core` | `/app` |
| ai | `./shared` | `/shared` |
| ai | `./services/ai` | `/app` |
| git | `./shared` | `/shared` |
| git | `./services/git` | `/app` |
| mcp | `./shared` | `/shared` |
| mcp | `./services/mcp` | `/app` |
| frontend | `./frontend` | `/app` |
| frontend | *(anonymous)* | `/app/node_modules` |

> **Important — frontend `node_modules`:** The anonymous `/app/node_modules` volume prevents the Windows host `node_modules` (which contains Windows-native binaries) from overwriting the Linux container's `node_modules`. Without it, Vite crashes with a `Cannot find native binding @rolldown/binding-linux-x64-gnu` error.

---

## Cloudflare Tunnel (webhooks)

To expose the webhook endpoint to GitHub without port forwarding:

```powershell
# Tunnel to port 80 (nginx gateway — routes /api/v1/git/webhook internally)
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:80
```

Paste the printed `https://*.trycloudflare.com` URL into GitHub:

```
Payload URL: https://<tunnel-url>/api/v1/git/webhook
Content type: application/json
```

Alternatively, use `start-all.ps1 -Tunnel` which auto-detects the URL, writes it to `frontend/.env.local` as `VITE_WEBHOOK_BASE_URL`, and surfaces it in the Settings page.

---

## Common Commands

```powershell
# Start dev stack (hot-reload, all ports exposed)
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up --build

# Start detached
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up -d --build

# Stop and remove containers
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml down

# Rebuild a single service
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml build core

# View logs for one service
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml logs -f core

# Open a shell inside a running container
docker exec -it oppmaiworkmanagementsystem-core-1 bash

# Check health
curl http://localhost:8000/health   # core
curl http://localhost/health/git    # via gateway
```

---

## Troubleshooting

### `No module named 'sqlalchemy'` (or any shared dep)
Stale image cache — the `pip install /shared` layer was cached before `pyproject.toml` was updated.
```powershell
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up --build
```
`--build` forces a fresh image build.

### `Cannot find native binding @rolldown/binding-linux-x64-gnu`
The frontend container is using Windows `node_modules` from the host mount. Make sure `docker-compose.dev.yml` has the anonymous volume:
```yaml
frontend:
  volumes:
    - ./frontend:/app
    - /app/node_modules   # ← this line is required
```

### Gateway exits immediately (dependency failed)
One or more microservices failed their health check before the gateway started. Run without `-d` to see the traceback, or check logs:
```powershell
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml logs core
```

### `services/.env` missing
```powershell
copy services\.env.example services\.env
# then edit services\.env and fill in JWT_SECRET_KEY, INTERNAL_API_KEY, etc.
```
