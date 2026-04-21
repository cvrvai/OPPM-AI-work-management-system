# Architecture

Last updated: 2026-04-10

## Purpose

This document describes the current runtime architecture of the OPPM AI Work Management System as it exists in code today. It replaces older notes that mixed the previous monolith assumptions with the current microservices implementation.

Use this file for system-level orientation. Use the supporting docs for detail:

- [API-REFERENCE.md](API-REFERENCE.md)
- [DATABASE-SCHEMA.md](DATABASE-SCHEMA.md)
- [ERD.md](ERD.md)
- [FLOWCHARTS.md](FLOWCHARTS.md)
- [FRONTEND-REFERENCE.md](frontend/FRONTEND-REFERENCE.md)
- [MICROSERVICES-REFERENCE.md](MICROSERVICES-REFERENCE.md)
- [services/README.md](services/README.md)
- [database/README.md](database/README.md)
- [MICROSERVICES-REVIEW.md](review/MICROSERVICES-REVIEW.md)
- [AI-SYSTEM-CONTEXT.md](AI-SYSTEM-CONTEXT.md)
- [AI-PIPELINE-REFERENCE.md](ai/AI-PIPELINE-REFERENCE.md)
- [TOOL-REGISTRY-REFERENCE.md](ai/TOOL-REGISTRY-REFERENCE.md)
- [SRS.md](SRS.md)
- [TESTING-GUIDE.md](TESTING-GUIDE.md)

## System Overview

OPPM is a workspace-scoped project management platform built around four backend services, a shared data layer, and a React frontend.

Current runtime shape:

```text
Browser
  -> Frontend (React + Vite)
  -> /api
      -> Gateway
          -> Core service
          -> AI service
          -> Git service
          -> MCP service
  -> PostgreSQL
  -> Redis
  -> External providers (GitHub, email, LLM APIs)
```

## Runtime Topology

### Frontend

The frontend lives in `frontend/` and runs as a React 19 + Vite + TypeScript application.

Primary responsibilities:

- authentication bootstrap and token persistence
- workspace selection and workspace-scoped navigation
- project, OPPM, team, commit, and settings UI
- calling backend APIs through `frontend/src/lib/api.ts`
- auto-refreshing access tokens on `401` via `POST /api/auth/refresh`

### Gateway Layer

There are two gateway implementations:

1. `services/gateway/`
   Native-development FastAPI reverse proxy with health-aware round robin.
2. `gateway/`
   Nginx config used in Docker and containerized deployments.

Both gateways must route the same URL patterns to the same services.

High-level route ownership:

- `/api/auth/*` -> core
- `/api/v1/workspaces/*/ai/*` -> ai
- `/api/v1/workspaces/*/rag/*` -> ai
- `/api/v1/workspaces/*/mcp/*` -> mcp
- `/api/v1/workspaces/*/github-accounts*` -> git
- `/api/v1/workspaces/*/commits*` -> git
- `/api/v1/workspaces/*/git/*` -> git
- `/api/v1/git/webhook` -> git
- all other `/api/*` -> core

### Core Service

`services/core/` is the primary business service.

It owns:

- authentication routes
- workspace CRUD and membership management
- invites and member skills
- project CRUD and project membership
- task CRUD and task daily reports
- OPPM objectives, timeline, and costs
- notifications
- dashboard stats
- Alembic migrations

### AI Service

`services/ai/` owns AI-facing functionality.

It provides:

- workspace and project chat owned directly by the AI service routers
- a TAOR agentic loop with a max of 7 iterations, low-confidence requery, and final wrap-up fallback
- input guardrails (injection detection) and output guardrails (sensitive data scrub)
- LLM-based query rewriting before retrieval
- semantic similarity cache (Redis, cosine ≥ 0.92, TTL 5 min) for RAG results
- tool registry with 24 tools across five categories (`oppm`, `task`, `cost`, `read`, `project`)
- native LLM function calling for OpenAI and Anthropic; XML-prompt fallback for Ollama and Kimi
- weekly summaries
- AI model configuration per workspace
- project plan suggestion and commit of suggested plans
- server-side file parsing, OPPM spreadsheet fill assistance, and OPPM image extraction
- workspace reindexing for retrieval
- RAG query endpoint
- internal commit analysis endpoint called by the git service
- user feedback endpoint (rating + comment logged to `audit_log`)

The AI service is not advisory-only. Its tool handlers can create and update shared business data directly through AI-side repositories on the shared database, including projects, objectives, tasks, timeline entries, costs, risks, and deliverables.

See [AI-PIPELINE-REFERENCE.md](ai/AI-PIPELINE-REFERENCE.md) and [TOOL-REGISTRY-REFERENCE.md](ai/TOOL-REGISTRY-REFERENCE.md) for component-level detail.

### Git Service

`services/git/` owns GitHub integration.

It provides:

- GitHub account registration
- repo configuration per project
- commit listing and recent analyses
- developer report endpoints
- GitHub webhook ingestion
- background handoff to the AI service for commit analysis

### MCP Service

`services/mcp/` exposes Model Context Protocol tools through HTTP.

It provides:

- tool discovery for the current workspace
- tool execution scoped to the current workspace

## Shared Layer

The shared Python package in `shared/` is the contract layer across services.

It contains:

- SQLAlchemy base and async session lifecycle
- authentication and authorization helpers
- Redis client bootstrap
- shared ORM models
- common schemas and enums
- common configuration

This is the most important architectural boundary in the backend.

Services do not each own independent databases. They share one data model and one PostgreSQL database through `shared/models/` and `shared/database.py`.

That shared-database model matters most for AI: the service boundary is real at the HTTP/router layer, but AI tool execution still writes through AI-owned repository code against the shared tables.

## Data Architecture

### Primary Database

The backend uses PostgreSQL accessed through SQLAlchemy async sessions.

Important facts:

- the ORM models live in `shared/models/`
- migrations live in `services/core/alembic/`
- 29 tables across 7 domain groups (see [DATABASE-SCHEMA.md](DATABASE-SCHEMA.md) and [ERD.md](ERD.md))
- RAG embeddings are stored in the same database
- audit and notification data are part of the same application database

### Redis

Redis is used as a support dependency, not as the source of truth.

**How Redis works in this system:**

Redis is an in-memory key-value store. The app uses `redis.asyncio` (async client) via `shared/redis_client.py`, which maintains a singleton connection pool.

Current roles in code:

| Role | Where | How |
|---|---|---|
| Token blacklist | `auth_service.signout()` | On signout, current access token hash is stored with a TTL equal to the remaining token lifetime. Subsequent requests check this key before accepting the token. |
| Rate limiting | `middleware/` | Request count per user/IP stored as a Redis key with a sliding window TTL. Returns `429` when limit exceeded. |
| Semantic cache | `services/ai/infrastructure/rag/semantic_cache.py` | Embedding similarity cache for RAG results. Cosine threshold ≥ 0.92, TTL 300 s. Keys prefixed `ai:sem_cache:`. Fail-safe — returns `None` if Redis is unavailable. |

If Redis is unavailable, the app can still start, but:
- signed-out access tokens may still work until they expire naturally
- rate limit enforcement degrades to in-memory (non-distributed)

**To check if Redis is running:**
```powershell
redis-cli ping  # should return PONG
```
The connection URL comes from `REDIS_URL` env var (default: `redis://localhost:6379`).

## Authentication And Authorization

Authentication is local JWT validation, not remote Supabase token introspection.

Current flow:

1. `POST /api/auth/login` or `POST /api/auth/signup` issues access and refresh tokens.
2. The frontend stores tokens in local storage.
3. `frontend/src/lib/api.ts` sends `Authorization: Bearer <token>`.
4. `shared/auth.py` validates the JWT locally using `python-jose` and `JWT_SECRET`.
5. Workspace-scoped routes resolve `WorkspaceContext` from `workspace_members`.

Authorization rules:

- authenticated routes use `get_current_user`
- workspace reads use `get_workspace_context`
- write routes use `require_write`
- admin routes use `require_admin`
- internal service-to-service routes use `X-Internal-API-Key`

Role behavior:

- `owner` and `admin` can perform admin actions
- `member` can perform write actions but not admin-only actions
- `viewer` is read-only

## Request Flow Patterns

### Standard UI Request

```text
React page
  -> api.ts
  -> /api/*
  -> gateway
  -> owning service
  -> shared database session
  -> PostgreSQL
  -> JSON response
```

### GitHub Commit Analysis

```text
GitHub push webhook
  -> git service webhook endpoint
  -> validate HMAC signature
  -> store commits
  -> background task
  -> AI internal endpoint /internal/analyze-commits
  -> commit analysis persisted
  -> frontend can query recent analyses and reports
```

### RAG Query

```text
Frontend or AI flow
  -> /api/v1/workspaces/{workspace_id}/rag/query
  -> AI service retrievers + reranker + memory loader
  -> document embeddings + structured queries + audit history
  -> synthesized context + sources returned
```

## Frontend Architecture Summary

The frontend follows a simple pattern:

- route-level pages in `frontend/src/pages/`
- reusable UI in `frontend/src/components/`
- server state with TanStack Query
- client session, workspace, and chat state with Zustand
- all HTTP requests through `frontend/src/lib/api.ts`
- route protection through `ProtectedRoute` in `frontend/src/App.tsx`
- workspace-scoped navigation safety via `useWorkspaceNavGuard` hook

See [FRONTEND-REFERENCE.md](frontend/FRONTEND-REFERENCE.md) for the detailed folder-level map.

## Load Balancing

### How Load Balancing Works

There are two load balancing implementations — one for native dev, one for Docker.

#### Python Gateway (native dev) — `services/gateway/`

```
Browser
  -> gateway:8080
      -> HealthyRoundRobin.next()
          -> next healthy instance from pool
              -> target service (core:8000, ai:8001, etc.)
```

`HealthyRoundRobin` in `services/gateway/load_balancer.py` uses Python's `itertools.cycle` to
select the next upstream in a round-robin loop, but only from the set of currently healthy instances.

Every 10 seconds an async background task pings each upstream's `/health` endpoint.
If a service returns HTTP 5xx or is unreachable, it is removed from the cycle.
When it recovers, it is added back.

To run multiple instances of a service, set the env var to a comma-separated list:
```
CORE_URLS=http://localhost:8000,http://localhost:8010
```

#### Nginx Gateway (Docker / production) — `gateway/nginx.conf`

Nginx uses its built-in `upstream` directive with the default round-robin strategy.
The same route ownership table applies — the Docker and native rules must stay in sync.

#### Route Ownership (both gateways)

| URL prefix | Service |
|---|---|
| `/api/v1/workspaces/*/ai/*` | ai |
| `/api/v1/workspaces/*/rag/*` | ai |
| `/api/v1/workspaces/*/mcp/*` | mcp |
| `/api/v1/workspaces/*/github-accounts*` | git |
| `/api/v1/workspaces/*/commits*` | git |
| `/api/v1/git/webhook` | git |
| all other `/api/*` | core |

## Real-Time Collaboration (Design Note)

The current architecture does not implement real-time multi-user collaboration (like Google Docs).
This section documents the algorithm and approach that would be used if it were added.

### Google Docs Technique: Operational Transformation (OT)

Google Docs uses **Operational Transformation**. The simpler modern alternative is **CRDTs** (Conflict-free Replicated Data Types), used by Figma, Notion, and others.

**How OT works (simplified):**

```
User A types "Hello"  →  Op: Insert("Hello", position=0)
User B types "World"  →  Op: Insert("World", position=0)

Server receives A's op first.
Server transforms B's op: Insert("World", position=5)  ← shifted past A's insert
Both users see "HelloWorld"
```

**How CRDTs work:**

Each operation is designed so that applying it in any order always produces the same result (commutativity + idempotency). No central transform needed — just merge.

### How to Add Real-Time to This System

The recommended approach given this stack:

```
1. Backend: Add WebSocket endpoint per project (FastAPI supports this natively)
   POST /api/v1/workspaces/{ws}/projects/{id}/ws

2. Connection: Frontend keeps a WebSocket open while on a project page

3. Broadcast: When any user saves a change (spreadsheet op, task update),
   the server fans out the operation to all connected clients for that project

4. Redis Pub/Sub: Use Redis as the message bus across multiple core instances
   - Core instance A receives op from User A
   - Publishes to Redis channel "project:{id}:ops"
   - Core instance B is subscribed and forwards to User B's WebSocket
```

**Redis Pub/Sub pattern (would be added to `shared/redis_client.py`):**
```python
# Publisher (when a user saves)
redis = await get_redis()
await redis.publish(f"project:{project_id}:ops", json.dumps(op))

# Subscriber (WebSocket handler)
pubsub = redis.pubsub()
await pubsub.subscribe(f"project:{project_id}:ops")
async for message in pubsub.listen():
    await ws.send_text(message["data"])
```

**The FortuneSheet spreadsheet** already exposes an `onOp` callback that fires for every cell change,
making it the natural source of ops to broadcast.

## Deployment Modes

### Native Development

Typical local stack:

- frontend dev server on `5173`
- python gateway on `8080`
- core on `8000`
- ai on `8001`
- git on `8002`
- mcp on `8003`

### Docker / Compose

Typical container stack:

- nginx gateway at the edge
- each backend service in its own container
- shared database and Redis dependencies

The two gateway implementations must stay behaviorally aligned.

## Strengths In The Current Architecture

- clean service split by responsibility
- one shared ORM model set instead of duplicated service-specific schemas
- clear workspace-scoped authorization model
- AI features are isolated from the core CRUD service
- GitHub webhook processing is decoupled through background work and internal calls
- frontend already follows a consistent API access pattern

## Current Architectural Risks

These are real, code-observed issues worth keeping in mind:

- gateway rules exist in two places, so route drift is possible
- some public field names do not match stored identifiers exactly, especially project member assignment
- workspace role naming is not fully normalized between backend responses and frontend types
- both `tasks.assignee_id` and `task_assignees` exist, but the current product flow uses the single-assignee field
- documentation had previously drifted from code, which is why this refresh was required

## Design Rules To Preserve

When adding new features, keep these boundaries intact:

- new business CRUD goes to the owning service, not the gateway
- shared tables belong in `shared/models/`
- migrations go through the core service migration flow
- frontend components should never call `fetch` directly outside `lib/api.ts`
- internal service calls should not be exposed through public routers accidentally
- workspace-scoped data must always resolve authorization through `WorkspaceContext`

## Recommended Reading Order

1. [SRS.md](SRS.md)
2. [MICROSERVICES-REFERENCE.md](MICROSERVICES-REFERENCE.md)
3. [FRONTEND-REFERENCE.md](frontend/FRONTEND-REFERENCE.md)
4. [API-REFERENCE.md](API-REFERENCE.md)
5. [ERD.md](ERD.md)
