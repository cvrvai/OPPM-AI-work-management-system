# Running the OPPM Microservices Stack

## Prerequisites

- Docker Desktop (v24+) with Docker Compose V2
- Ollama running locally for AI features (optional)

---

## Setup (First Time Only)

**1. Create the environment file:**
```bash
cp services/.env.example services/.env
```

**2. Edit `services/.env` with your real credentials:**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
INTERNAL_API_KEY=any-random-secret-string
OLLAMA_URL=http://host.docker.internal:11434
```

> `services/.env` is in `.gitignore` — never commit it.

---

## Start Everything

```bash
docker compose -f docker-compose.microservices.yml up -d --build
```

This starts:
| Container | Service | Internal Port |
|-----------|---------|---------------|
| gateway-1 | nginx reverse proxy | **80 (public)** |
| core-1 | workspaces / projects / tasks / OPPM | 8000 (internal) |
| ai-1 | LLM chat / RAG / commit analysis | 8001 (internal) |
| git-1 | GitHub webhooks / commits | 8002 (internal) |
| mcp-1 | MCP tools | 8003 (internal) |

The gateway waits for all 4 services to pass healthchecks before starting.

---

## Run the Frontend (Dev)

```bash
cd frontend
npm install   # first time only
npm run dev
```

Open **http://localhost:5173** — Vite proxies all `/api` calls to the gateway at port 80.

---

## Development Mode (Hot Reload)

To rebuild code changes without restarting manually, use the dev overlay which mounts source code as volumes:

```bash
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up -d
```

This also exposes individual service ports on the host:
- Core: http://localhost:8000
- AI: http://localhost:8001
- Git: http://localhost:8002
- MCP: http://localhost:8003

---

## Check Status

```bash
# All container health
docker compose -f docker-compose.microservices.yml ps

# Quick health check for all services
curl http://localhost/health/core
curl http://localhost/health/ai
curl http://localhost/health/git
curl http://localhost/health/mcp
```

---

## View Logs

```bash
# All services
docker compose -f docker-compose.microservices.yml logs -f

# Single service
docker compose -f docker-compose.microservices.yml logs -f core
docker compose -f docker-compose.microservices.yml logs -f ai
docker compose -f docker-compose.microservices.yml logs -f git
docker compose -f docker-compose.microservices.yml logs -f mcp
docker compose -f docker-compose.microservices.yml logs -f gateway
```

---

## Stop

```bash
docker compose -f docker-compose.microservices.yml down
```

---

## Rebuild After Code Changes

```bash
# Rebuild and restart a single service (e.g., core)
docker compose -f docker-compose.microservices.yml up -d --build core

# Rebuild all
docker compose -f docker-compose.microservices.yml up -d --build
```

> **Note:** After restarting services, the gateway automatically re-resolves Docker DNS —
> you do NOT need to restart the gateway separately.

---

## Architecture

```
Browser → http://localhost:5173 (Vite dev server)
               ↓  /api/* proxied to localhost:80
          nginx gateway (port 80)
               ├── /api/v1/.../ai/      → ai:8001
               ├── /api/v1/.../rag/     → ai:8001
               ├── /api/v1/.../git/     → git:8002
               ├── /api/v1/.../commits  → git:8002
               ├── /api/v1/git/webhook  → git:8002
               ├── /api/v1/.../mcp/     → mcp:8003
               └── /api/*  (everything else) → core:8000
```

---

## Troubleshooting

**502 Bad Gateway**
The gateway lost contact with a service (e.g., after a container restart). Restart the gateway:
```bash
docker compose -f docker-compose.microservices.yml restart gateway
```
This is no longer needed after the DNS-resolver fix, but useful as a fallback.

**Service fails to start (Exit 1)**
Check the logs:
```bash
docker compose -f docker-compose.microservices.yml logs core
```
Most common cause: missing or incorrect `services/.env`.

**Ollama not responding (AI features silent)**
Ensure Ollama is running on your host:
```bash
ollama serve
```
The `OLLAMA_URL=http://host.docker.internal:11434` in `services/.env` reaches your local Ollama from inside Docker.
