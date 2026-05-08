# Development Guide

## Table of Contents
1. [Updating Docker After Code Changes](#updating-docker-after-code-changes)
2. [Running Services Natively](#running-services-natively)

---

## Updating Docker After Code Changes

### Rebuild a single service (most common)

When you change code in **one service**, only rebuild that service:

```bash
# Replace <service> with: workspace | intelligence | gateway
docker compose -f docker-compose.microservices.yml up -d --build <service>
```

Examples:
```bash
# Changed something in services/workspace/
docker compose -f docker-compose.microservices.yml up -d --build workspace

# Changed something in services/intelligence/
docker compose -f docker-compose.microservices.yml up -d --build intelligence

# Changed nginx.conf in gateway/
docker compose -f docker-compose.microservices.yml up -d --build gateway
```

### Rebuild multiple services at once

```bash
docker compose -f docker-compose.microservices.yml up -d --build workspace intelligence
```

### Rebuild everything

Only needed when you change `shared/` (the shared package used by all services):

```bash
docker compose -f docker-compose.microservices.yml up -d --build
```

### Restart a service without rebuilding

Use this if you only changed environment variables in `services/.env`:

```bash
docker compose -f docker-compose.microservices.yml restart core
```

### Check if your service is healthy after rebuild

```bash
# Show all containers and their status
docker compose -f docker-compose.microservices.yml ps

# Tail logs to confirm startup
docker compose -f docker-compose.microservices.yml logs -f core
```

### What triggers a full rebuild vs. a single rebuild?

| What changed | Command |
|---|---|
| `services/workspace/**` | `--build workspace` |
| `services/intelligence/**` | `--build intelligence` |
| `gateway/nginx.conf` | `--build gateway` |
| `shared/**` | `--build` (all services) |
| `services/.env` | `restart <service>` (no rebuild needed) |
| `frontend/src/**` | No Docker change needed — Vite hot-reloads |

---

## Running Services Natively

Each service has a `start.ps1` script. Run it from anywhere — it handles everything.

### Prerequisites (one-time)

Install all dependencies into your global Python environment:

```powershell
pip install -r services/workspace/requirements.txt
pip install -r services/intelligence/requirements.txt
```

---

### Running a service

Open one terminal per service (3 total). Run each from the workspace root:

```powershell
./services/workspace/start.ps1     # port 8000 — workspaces, projects, tasks, OPPM, GitHub
./services/intelligence/start.ps1  # port 8001 — chat, RAG, commit analysis, MCP tools
```

```powershell
# Frontend (port 5173)
cd frontend ; npm run dev
```

`npm run dev` now proxies `/api` through the nginx gateway on `http://localhost:80`.

If you're already inside a service folder (e.g. `services/workspace/`), just run:

```powershell
./start.ps1
```

All service-to-service calls (e.g. git → ai) go through the gateway on port 8080, not directly. The gateway does round-robin load balancing — to run multiple instances of a service, add more URLs to `.env`:

```dotenv
# Run two core instances for load balancing
CORE_URLS=http://localhost:8000,http://localhost:8010
```

Then start the second instance on the extra port:
```powershell
# In services/workspace/, temporarily override the port
uvicorn main:app --reload --port 8010
```

---

### Mixing native + Docker

```powershell
# 1. Start everything in Docker
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up -d

# 2. Stop the one you want to run natively
docker compose -f docker-compose.microservices.yml stop workspace

# 3. Run it with the script
./services/workspace/start.ps1
```

---

### Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'shared'` | Make sure you're running `./start.ps1`, not `uvicorn` directly. |
| `ModuleNotFoundError: No module named 'fastapi'` (or similar) | Run `pip install -r services/<name>/requirements.txt` first. |
| `cannot be loaded because running scripts is disabled` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once in PowerShell. |
| Gateway returns 502 | The target service isn't running. Start it with its `start.ps1`. |

---

### Service port reference

| Service | Port | What it does |
|---|---|---|
| gateway (Docker) | 80 | nginx reverse proxy + load balancer |
| workspace | 8000 | workspaces, projects, tasks, OPPM, GitHub, notifications |
| intelligence | 8001 | chat, RAG, AI analysis, MCP tools |
| frontend | 5173 | Vite dev server |

---

## Database Migrations

Migrations are applied via Alembic inside the `workspace` service.

### Apply pending migrations (Docker)

```powershell
docker compose -f docker-compose.microservices.yml exec workspace alembic upgrade head
```

### Apply pending migrations (native)

```powershell
cd services/workspace
.\start.ps1   # ensure env vars loaded, then in another terminal:
alembic upgrade head
```

### Create a new migration

```powershell
cd services/workspace
alembic revision --autogenerate -m "add column foo to projects"
# Review the generated file in services/workspace/alembic/versions/
alembic upgrade head
```

### Check migration status

```powershell
alembic current   # shows which migration is applied
alembic history   # full migration log
```

---

## Docker Dev Overlay (`docker-compose.dev.yml`)

The `docker-compose.dev.yml` file is a **development overlay** that mounts local source code into running containers for hot-reload during development. Use it instead of rebuilding on every code change:

```powershell
# Start all services with hot-reload volume mounts
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up -d
```

What it does:
- Mounts `services/workspace/` → `/app/` in the workspace container (uvicorn `--reload` picks up changes)
- Same for `services/intelligence/`, `services/integrations/`, `services/automation/`
- Does **not** mount `shared/` — rebuild required if shared code changes (`--build` all)

Note: The frontend is not included in the Docker overlay; Vite hot-reload operates independently on port 5173.
