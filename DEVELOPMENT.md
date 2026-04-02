# Development Guide

## Table of Contents
1. [Updating Docker After Code Changes](#updating-docker-after-code-changes)
2. [Running Services Natively](#running-services-natively)

---

## Updating Docker After Code Changes

### Rebuild a single service (most common)

When you change code in **one service**, only rebuild that service:

```bash
# Replace <service> with: core | ai | git | mcp | gateway
docker compose -f docker-compose.microservices.yml up -d --build <service>
```

Examples:
```bash
# Changed something in services/core/
docker compose -f docker-compose.microservices.yml up -d --build core

# Changed something in services/ai/
docker compose -f docker-compose.microservices.yml up -d --build ai

# Changed nginx.conf in gateway/
docker compose -f docker-compose.microservices.yml up -d --build gateway
```

### Rebuild multiple services at once

```bash
docker compose -f docker-compose.microservices.yml up -d --build core ai
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
| `services/core/**` | `--build core` |
| `services/ai/**` | `--build ai` |
| `services/git/**` | `--build git` |
| `services/mcp/**` | `--build mcp` |
| `gateway/nginx.conf` | `--build gateway` |
| `shared/**` | `--build` (all services) |
| `services/.env` | `restart <service>` (no rebuild needed) |
| `frontend/src/**` | No Docker change needed — Vite hot-reloads |

---

## Running Services Natively

Run services directly on your machine without Docker. Useful for faster iteration and debugging with a proper Python debugger.

### Prerequisites

- Python 3.11+ (3.12 recommended; 3.11 works fine)
- Node.js 20+ (for frontend)
- All other services still running in Docker, **or** all running natively

### One-time setup

**1. Install the shared package** (run from workspace root):

```bash
pip install -e shared/
```

The `-e` flag installs it in editable mode — changes to `shared/` take effect immediately without reinstalling.

> If you see `Package 'oppm-shared' requires a different Python` after running this, it means an old cached version is fighting the install. Force-reinstall:
> ```bash
> pip install -e shared/ --ignore-requires-python
> ```
> Or upgrade pip first: `pip install --upgrade pip`, then retry.

**2. Install service dependencies:**

```bash
pip install -r services/core/requirements.txt
pip install -r services/ai/requirements.txt
pip install -r services/git/requirements.txt
pip install -r services/mcp/requirements.txt
```

**3. Create your `.env` file** (if you haven't already):

```bash
cp services/.env.example services/.env
# Then edit services/.env with your real credentials
```

---

### Running each service

Open a separate terminal for each service you want to run natively.

Each service needs `PYTHONPATH` pointing at the **workspace root** so that `import shared` resolves correctly. Use `--app-dir` to tell uvicorn which service to run **without leaving the workspace root** — this keeps `PYTHONPATH` correct and avoids the most common mistake.

> **Common mistake:** setting `PYTHONPATH` then running `cd services/core`, which moves you out of the workspace root before uvicorn launches its subprocess. Always run uvicorn from the workspace root using `--app-dir`.

#### Core service (port 8000)

Handles: workspaces, projects, tasks, OPPM, notifications, dashboard

```powershell
# PowerShell — run from workspace root
$env:PYTHONPATH = (Get-Location).Path
uvicorn main:app --app-dir services/core --reload --port 8000
```
```bash
# macOS/Linux — run from workspace root
PYTHONPATH=$(pwd) uvicorn main:app --app-dir services/core --reload --port 8000
```

#### AI service (port 8001)

Handles: LLM chat, RAG, commit analysis

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn main:app --app-dir services/ai --reload --port 8001
```
```bash
PYTHONPATH=$(pwd) uvicorn main:app --app-dir services/ai --reload --port 8001
```

#### Git service (port 8002)

Handles: GitHub webhooks, commits, repo configs

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn main:app --app-dir services/git --reload --port 8002
```
```bash
PYTHONPATH=$(pwd) uvicorn main:app --app-dir services/git --reload --port 8002
```

#### MCP service (port 8003)

Handles: Model Context Protocol tools

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn main:app --app-dir services/mcp --reload --port 8003
```
```bash
PYTHONPATH=$(pwd) uvicorn main:app --app-dir services/mcp --reload --port 8003
```

> **Why `PYTHONPATH`?** The services use `import shared` which resolves to the `shared/` folder at the workspace root. Docker sets `ENV PYTHONPATH=/` so `/shared` is findable. Natively you replicate this by pointing `PYTHONPATH` at the workspace root. `--app-dir` keeps your working directory at the root the entire time so the variable stays valid.

#### Frontend (port 5173)

```bash
cd frontend
npm run dev
```

---

### Loading environment variables

Each service reads from `services/.env` via `pydantic-settings`. Set `PYTHONPATH` and load the env file in one block from the workspace root:

**Windows PowerShell (run from workspace root):**
```powershell
# 1. Set PYTHONPATH to workspace root
$env:PYTHONPATH = (Get-Location).Path

# 2. Load all variables from services/.env into the current process
Get-Content services/.env | ForEach-Object {
  if ($_ -match '^([^#=][^=]*)=(.*)$') {
    [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
  }
}

# 3. Run the service (stay in workspace root — use --app-dir)
uvicorn main:app --app-dir services/core --reload --port 8000
```

**macOS/Linux:**
```bash
# From workspace root
export PYTHONPATH=$(pwd)
set -a && source services/.env && set +a
uvicorn main:app --app-dir services/core --reload --port 8000
```

---

### Mixing native + Docker

You can run just the service you're working on natively, and keep the rest in Docker:

1. Start the full Docker stack as usual:
   ```bash
   docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up -d
   ```
   The dev overlay exposes each service port on the host (8000–8003).

2. Stop the one you want to run natively:
   ```bash
   docker compose -f docker-compose.microservices.yml stop core
   ```

3. Run it natively on the same port (from workspace root):
   ```powershell
   $env:PYTHONPATH = (Get-Location).Path
   uvicorn main:app --app-dir services/core --reload --port 8000
   ```

4. The nginx gateway and all other services continue to work — they'll connect to your native process on `localhost:8000`.

> **Note:** The gateway container resolves service names via Docker DNS. When running a service natively, the gateway won't reach it. Use the Vite dev proxy (`localhost:5173`) which goes through `localhost:80` (gateway), or call services directly on their host port.

---

### Service port reference

| Service | Docker internal | Host (dev overlay) | What it does |
|---|---|---|---|
| gateway | 80 | 80 | nginx reverse proxy |
| core | 8000 | 8000 | workspaces, projects, tasks, OPPM |
| ai | 8001 | 8001 | chat, RAG, AI analysis |
| git | 8002 | 8002 | GitHub, webhooks, commits |
| mcp | 8003 | 8003 | MCP tool endpoints |
| frontend | — | 5173 | Vite dev server |
