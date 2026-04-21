# Microservices Migration Guide

## Overview

The monolithic `backend/` has been split into 4 focused microservices under `services/`:

| Service | Port | Responsibility |
|---------|------|---------------|
| **core** | 8000 | Workspaces, projects, tasks, OPPM, notifications, dashboard, auth |
| **ai** | 8001 | LLM chat, RAG pipeline, commit analysis, AI model config, reindex |
| **git** | 8002 | GitHub accounts, repo configs, webhooks, commit events |
| **mcp** | 8003 | MCP tool registry, tool execution for AI integrations |

All services sit behind an **nginx gateway** on port 80.

## Architecture

```
                    ┌──────────┐
  Client ──────────►│  nginx   │ :80
                    │  gateway │
                    └────┬─────┘
           ┌─────────┬──┴──┬──────────┐
           ▼         ▼     ▼          ▼
       ┌──────┐  ┌─────┐ ┌─────┐ ┌─────┐
       │ core │  │ ai  │ │ git │ │ mcp │
       │ :8000│  │:8001│ │:8002│ │:8003│
       └──┬───┘  └──┬──┘ └──┬──┘ └──┬──┘
          │         │       │       │
          └─────────┴───┬───┴───────┘
                        ▼
                   ┌──────────┐
                   │ Supabase │
                   │ Postgres │
                   └──────────┘
```

## Shared Package

All services depend on `shared/` — a pip-installable package containing:

- **`shared.config`** — `SharedSettings` (Supabase URLs, env, internal API key)
- **`shared.database`** — `get_db()` singleton (Supabase client with service_role_key)
- **`shared.auth`** — `CurrentUser`, `get_current_user`, `WorkspaceContext`, `get_workspace_context`, `require_admin`, `require_write`, `verify_internal_key`
- **`shared.schemas.common`** — Enums (`ProjectStatus`, `Priority`, `TaskStatus`, `WorkspaceRole`) and common models (`PaginatedResponse`, `ErrorResponse`, `SuccessResponse`)

Each service extends `SharedSettings` with its own config (e.g., `AISettings` adds LLM API keys).

## Inter-Service Communication

Only **one** inter-service call exists:

```
Git service (webhook) ──HTTP POST──► AI service (/internal/analyze-commits)
                       X-Internal-API-Key header
```

All other data flows go through the shared Supabase database.

## Import Changes (from monolith)

| Monolith import | Microservice import |
|----------------|-------------------|
| `from database import get_db` | `from shared.database import get_db` |
| `from middleware.auth import get_current_user` | `from shared.auth import get_current_user` |
| `from middleware.workspace import get_workspace_context` | `from shared.auth import get_workspace_context` |
| `from schemas.common import ...` | `from shared.schemas.common import ...` |
| `from config import get_settings` | `from config import get_settings` (unchanged — each service has its own) |

## Running

### Development (with hot reload)

```bash
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up
```

Services are accessible directly:
- Core: http://localhost:8000
- AI: http://localhost:8001
- Git: http://localhost:8002
- MCP: http://localhost:8003
- Gateway: http://localhost (port 80)

### Production

```bash
cp services/.env.example services/.env
# Edit services/.env with real credentials
docker compose -f docker-compose.microservices.yml up -d
```

All traffic goes through the gateway on port 80.

## Health Checks

Each service exposes `GET /health`:

```bash
curl http://localhost:8000/health  # {"status":"ok","service":"core"}
curl http://localhost:8001/health  # {"status":"ok","service":"ai"}
curl http://localhost:8002/health  # {"status":"ok","service":"git"}
curl http://localhost:8003/health  # {"status":"ok","service":"mcp"}
```

## File Structure

```
services/
├── .env.example
├── shared/                 # Shared package (pip install -e /shared)
│   ├── pyproject.toml
│   ├── __init__.py
│   ├── auth.py             # Auth + workspace context
│   ├── config.py           # SharedSettings
│   ├── database.py         # Supabase client singleton
│   └── schemas/
│       └── common.py       # Enums + common models
├── core/                   # Core service (port 8000)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   ├── middleware/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── routers/v1/
├── ai/                     # AI service (port 8001)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   ├── infrastructure/     # LLM adapters + RAG pipeline
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── routers/
│       ├── v1/             # Public API routes
│       └── internal.py     # Service-to-service routes
├── git/                    # Git service (port 8002)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── routers/v1/
├── mcp/                    # MCP service (port 8003)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   ├── infrastructure/mcp/ # MCP tool implementations
│   └── routers/v1/
├── gateway/
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.microservices.yml
└── docker-compose.dev.yml
```

## Backward Compatibility

The original `backend/` directory is **preserved** and continues to work as a monolith. The microservices migration is additive — you can run either architecture.
