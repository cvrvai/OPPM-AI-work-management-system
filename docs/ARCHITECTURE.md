# OPPM AI Work Management System — Architecture

> Multi-tenant, workspace-scoped AI-powered project management platform following the **One Page Project Manager (OPPM)** methodology.
>
> ⚠️ **Stack**: Self-hosted PostgreSQL · Custom JWT Auth · Redis · Docker — **No Supabase**.

## Table of Contents
- [System Overview](#system-overview)
- [Infrastructure Stack](#infrastructure-stack)
- [Architecture Layers](#architecture-layers)
- [Database Design](#database-design)
- [Backend Architecture](#backend-architecture)
- [Frontend Architecture](#frontend-architecture)
- [API Design](#api-design)
- [Authentication & Authorization](#authentication--authorization)
- [Redis Usage](#redis-usage)
- [RAG Architecture](#rag-architecture)
- [Multi-Tenancy Model](#multi-tenancy-model)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        OPPM AI System (Microservices)                   │
│                                                                          │
│  ┌─────────┐   ┌────────────────┐   ┌──────────────────────────────┐   │
│  │  React  │──▶│    Gateway     │──▶│  core:8000                   │   │
│  │Frontend │◀──│  :8080 native  │   │  (workspaces, projects,      │   │
│  │ (SPA)   │   │  :80 Docker    │──▶│   tasks, auth, OPPM)         │   │
│  └─────────┘   │                │   ├──────────────────────────────┤   │
│                │  FastAPI       │──▶│  ai:8001                     │   │
│                │  reverse proxy │   │  (LLM chat, RAG, models)     │   │
│                │  + round-robin │──▶│  git:8002                    │   │
│                │  load balancer │   │  (webhooks, commits)         │   │
│                └────────────────┘──▶│  mcp:8003                    │   │
│                                     │  (MCP protocol tools)        │   │
│                                     └────────────┬─────────────────┘   │
│                                                  │                      │
│                          ┌───────────────────────┼──────────────────┐  │
│                          ▼                       ▼                  │  │
│                 ┌─────────────────┐   ┌─────────────────┐          │  │
│                 │   PostgreSQL    │   │      Redis       │          │  │
│                 │   :5432         │   │      :6379       │          │  │
│                 │  (primary DB)   │   │  sessions/cache/ │          │  │
│                 │  pgvector ext   │   │  rate-limit/     │          │  │
│                 └─────────────────┘   │  celery broker   │          │  │
│                                       └─────────────────┘          │  │
│  Docker prod: nginx gateway  |  Native dev: Python gateway (:8080)  │  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Database | PostgreSQL 16 (Docker) | pgvector extension for embeddings |
| Cache / Sessions | Redis 7 (Docker) | Token store, rate limiter, Celery broker |
| Auth | Custom JWT (RS256 or HS256) | Access + refresh tokens, no external auth provider |
| ORM / Queries | SQLAlchemy 2.x async + asyncpg | Direct SQL for complex queries |
| Migrations | Alembic | Version-controlled schema migrations |
| Background Jobs | Celery + Redis | Async tasks (embeddings, notifications, webhooks) |
| Gateway | FastAPI reverse proxy | Round-robin load balancer |
| Frontend | React + Vite + TypeScript | Zustand for state |
| Container | Docker + Docker Compose | All services containerised |
| Web Server | Nginx (Docker prod) | Static files + proxy |

---

## Architecture Layers

### Backend (4-Layer Clean Architecture)

```
┌───────────────────────────────────────────────────────┐
│  Routers (API Layer)                                  │
│  routers/v1/*.py — HTTP handlers, Pydantic validation │
├───────────────────────────────────────────────────────┤
│  Services (Business Logic)                            │
│  services/*.py — orchestration, rules, workflows      │
├───────────────────────────────────────────────────────┤
│  Repositories (Data Access)                           │
│  repositories/*.py — SQLAlchemy async queries, CRUD   │
├───────────────────────────────────────────────────────┤
│  Infrastructure (External Integrations)               │
│  infrastructure/llm/*.py  — AI model adapters         │
│  infrastructure/redis.py  — Redis client singleton    │
│  infrastructure/db.py     — SQLAlchemy engine/session │
│  middleware/*.py          — auth, rate limit, logging │
└───────────────────────────────────────────────────────┘
```

### Frontend (Feature-Module Pattern)

```
src/
├── components/        # Shared UI components
│   ├── layout/        # Header, Sidebar, Layout
│   └── workspace/     # Workspace selector
├── hooks/             # Shared custom hooks
├── lib/               # API client, utils (NO Supabase client)
├── pages/             # Route-level page components
├── stores/            # Zustand stores (auth, workspace)
└── types/             # TypeScript interfaces
```

---

## Database Design

> All tables live in a single self-hosted PostgreSQL instance.
> There is **no Supabase client, no RLS via Supabase, and no Supabase Auth**.
> Row-level security is enforced in the **repository layer** by always including `workspace_id` and verifying membership in the service layer.

### Users & Auth Tables

```
┌────────────────────────────────┐   ┌─────────────────────────────────┐
│  users                         │   │  refresh_tokens                 │
│────────────────────────────────│   │─────────────────────────────────│
│ id          UUID PK default    │   │ id          UUID PK             │
│             gen_random_uuid()  │   │ user_id     UUID FK → users.id  │
│ email       TEXT UNIQUE NN     │   │ token_hash  TEXT UNIQUE NN      │
│ password_hash TEXT NN          │   │ expires_at  TIMESTAMPTZ NN      │
│ full_name   TEXT               │   │ created_at  TIMESTAMPTZ         │
│ avatar_url  TEXT               │   │ revoked     BOOLEAN DEFAULT false│
│ is_active   BOOLEAN DEFAULT T  │   └─────────────────────────────────┘
│ is_verified BOOLEAN DEFAULT F  │
│ created_at  TIMESTAMPTZ        │   ┌─────────────────────────────────┐
│ updated_at  TIMESTAMPTZ        │   │  email_verifications            │
└────────────────────────────────┘   │─────────────────────────────────│
                                     │ id        UUID PK               │
                                     │ user_id   UUID FK → users.id    │
                                     │ token     TEXT UNIQUE NN        │
                                     │ expires_at TIMESTAMPTZ NN       │
                                     └─────────────────────────────────┘
```

### Workspace & Membership Tables

```
                    ┌────────────────┐
                    │   workspaces   │
                    │────────────────│
                    │ id (PK UUID)   │
                    │ name           │
                    │ slug (unique)  │
                    │ description    │
                    │ created_by FK  │ ──▶ users.id
                    │ created_at     │
                    └───────┬────────┘
                            │ 1:N
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
  ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
  │workspace_members │ │workspace_    │ │  projects        │
  │──────────────────│ │  invites     │ │──────────────────│
  │ id (PK)          │ │──────────────│ │ id (PK)          │
  │ workspace_id(FK) │ │ id (PK)      │ │ workspace_id(FK) │
  │ user_id (FK)     │ │workspace_id  │ │ title            │
  │ role             │ │ email        │ │ status           │
  │  (owner/admin/   │ │ role         │ │ priority         │
  │   member/viewer) │ │ token        │ │ progress         │
  │ joined_at        │ │ expires_at   │ │ lead_id (FK)     │
  └────────┬─────────┘ │ accepted     │ │ created_at       │
           │            └──────────────┘ └───────┬──────────┘
           │                                     │ 1:N
     ┌─────┘          ┌───────────────────────────┘
     ▼                ▼
┌──────────────┐  ┌───────────────┐  ┌──────────────┐ ┌──────────────┐
│project_      │  │oppm_objectives│  │   tasks      │ │project_costs │
│  members     │  │───────────────│  │──────────────│ │──────────────│
│──────────────│  │ id (PK)       │  │ id (PK)      │ │ id (PK)      │
│ id (PK)      │  │ project_id(FK)│  │ project_id   │ │ project_id   │
│ project_id   │  │ title         │  │ title        │ │ category     │
│ user_id (FK) │  │ owner_id      │  │ status       │ │planned_amount│
│ role         │  │ sort_order    │  │ progress     │ │actual_amount │
└──────────────┘  └───────┬───────┘  │ assignee_id  │ └──────────────┘
                          │          │oppm_objective │
                    ┌─────▼────────┐ │  _id (FK)     │
                    │oppm_timeline │ └──────┬───────┘
                    │  _entries    │        │
                    │──────────────│  ┌─────▼────────┐
                    │ id (PK)      │  │task_assignees │
                    │ objective_id │  │──────────────│
                    │ year, month  │  │ task_id (FK)  │
                    │ status       │  │ user_id (FK)  │
                    └──────────────┘  └──────────────┘
```

### Git, AI, Audit Tables

```
┌────────────────────┐  ┌─────────────────┐  ┌───────────────────┐
│  github_accounts   │  │  repo_configs   │  │  commit_events    │
│────────────────────│  │─────────────────│  │───────────────────│
│ id                 │  │ id              │  │ id                │
│ workspace_id (FK)  │  │ repo_name       │  │ repo_config_id    │
│ account_name       │  │ project_id (FK) │  │ commit_hash       │
│ github_username    │  │ github_account  │  │ commit_message    │
│ encrypted_token    │  │   _id (FK)      │  │ author            │
└────────────────────┘  │ webhook_secret  │  │ branch            │
                        └─────────────────┘  │ files_changed     │
                                             │ pushed_at         │
┌────────────────────┐                       └─────────┬─────────┘
│  commit_analyses   │◀──────────────────────────────────┘
│────────────────────│
│ id                 │
│ commit_event_id    │
│ ai_model           │
│ quality_score      │
│ alignment_score    │
│ progress_delta     │
│ summary            │
│ quality_flags      │
│ suggestions        │
└────────────────────┘

┌────────────────────┐  ┌─────────────────┐  ┌───────────────────┐
│  notifications     │  │   ai_models     │  │    audit_log      │
│────────────────────│  │─────────────────│  │───────────────────│
│ id                 │  │ id              │  │ id                │
│ workspace_id       │  │ workspace_id    │  │ workspace_id      │
│ user_id            │  │ name            │  │ user_id           │
│ type               │  │ provider        │  │ action            │
│ title              │  │  (ollama/       │  │ entity_type       │
│ message            │  │  anthropic/     │  │ entity_id         │
│ is_read            │  │  openai/kimi/   │  │ old_data (JSONB)  │
│ link               │  │  custom)        │  │ new_data (JSONB)  │
│ metadata (JSONB)   │  │ model_id        │  │ ip_address        │
└────────────────────┘  │ endpoint_url    │  └───────────────────┘
                        │ is_active       │
                        └─────────────────┘

┌───────────────────────────────┐
│     document_embeddings       │
│───────────────────────────────│
│ id (PK)                       │
│ workspace_id (FK)             │
│ entity_type (task/objective/  │
│   commit/project)             │
│ entity_id                     │
│ content                       │
│ metadata (JSONB)              │
│ embedding VECTOR(1536)        │  ← requires pgvector extension
└───────────────────────────────┘
```

### Indexes (Performance)

```sql
-- Auth
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);

-- Workspace lookups
CREATE INDEX idx_workspace_members_user_id ON workspace_members(user_id);
CREATE INDEX idx_workspace_members_workspace_id ON workspace_members(workspace_id);

-- Task / project lookups
CREATE INDEX idx_tasks_project_id ON tasks(project_id);
CREATE INDEX idx_tasks_assignee_id ON tasks(assignee_id);
CREATE INDEX idx_projects_workspace_id ON projects(workspace_id);

-- Notifications
CREATE INDEX idx_notifications_user_id_unread ON notifications(user_id) WHERE is_read = false;

-- Embeddings (cosine similarity via pgvector)
CREATE INDEX idx_document_embeddings_workspace ON document_embeddings(workspace_id);
CREATE INDEX idx_document_embeddings_vector ON document_embeddings
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## Backend Architecture

### Directory Structure

```
services/
├── shared/                          # Shared package imported by ALL services
│   ├── auth.py                      # JWT encode/decode, token validation (NO Supabase)
│   ├── database.py                  # SQLAlchemy async engine + session factory
│   ├── redis_client.py              # Redis connection singleton (aioredis)
│   ├── config.py                    # SharedSettings(BaseSettings) — DB + Redis + JWT
│   ├── models/                      # SQLAlchemy ORM models (shared across services)
│   │   ├── user.py
│   │   ├── workspace.py
│   │   ├── project.py
│   │   ├── task.py
│   │   └── ...
│   └── schemas/common.py            # Shared Pydantic schemas
│
├── gateway/                         # API Gateway + Load Balancer (port 8080)
│   ├── main.py                      # FastAPI reverse proxy, round-robin LB
│   ├── config.py                    # CORE_URLS, AI_URLS, GIT_URLS, MCP_URLS
│   ├── .env                         # Upstream service URLs only
│   └── start.ps1
│
├── core/                            # Core service (port 8000)
│   ├── main.py                      # App factory + middleware chain
│   ├── config.py                    # CoreSettings (DB, Redis, JWT, CORS)
│   ├── .env                         # Per-service credentials
│   ├── start.ps1
│   ├── alembic/                     # Database migrations
│   │   ├── env.py
│   │   ├── versions/
│   │   └── alembic.ini
│   ├── middleware/
│   │   ├── auth.py                  # Decode JWT → CurrentUser (local validation, no HTTP call)
│   │   ├── workspace.py             # Workspace membership → WorkspaceContext
│   │   ├── rate_limit.py            # Redis token-bucket rate limiter
│   │   └── logging.py               # Request logging + timing
│   ├── repositories/
│   │   ├── base.py                  # BaseRepository (generic SQLAlchemy CRUD)
│   │   ├── user_repo.py             # User CRUD + password hashing
│   │   ├── workspace_repo.py        # Workspace + Member + Invite
│   │   ├── project_repo.py          # Project + ProjectMember
│   │   ├── task_repo.py             # Task (with progress calc)
│   │   ├── oppm_repo.py             # Objective + Timeline + Cost
│   │   └── notification_repo.py     # Notification + Audit
│   ├── services/
│   │   ├── auth_service.py          # register, login, refresh, signout, verify email
│   │   ├── workspace_service.py     # Workspace lifecycle + invites
│   │   ├── project_service.py       # Project CRUD + members
│   │   ├── task_service.py          # Task CRUD + progress recalc
│   │   ├── oppm_service.py          # OPPM objectives, timeline, costs
│   │   └── notification_service.py  # Notification CRUD
│   ├── schemas/                     # Pydantic request/response models
│   └── routers/
│       ├── auth.py                  # POST /api/auth/register|login|refresh|signout
│       │                            # GET  /api/auth/me
│       │                            # PATCH /api/auth/profile
│       │                            # POST /api/auth/verify-email
│       └── v1/
│           ├── workspaces.py
│           ├── projects.py
│           ├── tasks.py
│           ├── oppm.py
│           ├── notifications.py
│           └── dashboard.py
│
├── ai/                              # AI service (port 8001)
│   ├── main.py
│   ├── .env
│   ├── start.ps1
│   ├── infrastructure/
│   │   ├── llm/                     # LLM adapters (unchanged)
│   │   └── rag/                     # RAG pipeline (uses pgvector directly)
│   │       ├── embedder.py
│   │       ├── reranker.py
│   │       ├── memory.py            # Reads audit_log via SQLAlchemy
│   │       ├── agent.py
│   │       └── retrievers/
│   └── routers/v1/
│
├── git/                             # Git service (port 8002)
│   ├── main.py
│   ├── .env
│   ├── start.ps1
│   └── routers/v1/
│
└── mcp/                             # MCP service (port 8003)
    ├── main.py
    ├── .env
    ├── start.ps1
    └── routers/
```

### Request Flow

```
Browser → Vite dev proxy (:5173)
    │
    ▼
Gateway (:8080 native / nginx:80 Docker)
├── Path routing (most-specific first):
│   /api/auth/                    → core:8000
│   /api/v1/.../projects/.../ai/  → ai:8001
│   /api/v1/.../rag/              → ai:8001
│   /api/v1/.../ai/               → ai:8001
│   /api/v1/.../mcp/              → mcp:8003
│   /api/v1/.../github-accounts   → git:8002
│   /api/v1/.../commits           → git:8002
│   /api/v1/git/webhook           → git:8002
│   /mcp (SSE)                    → mcp:8003
│   /api/ (catch-all)             → core:8000
│
    ▼
Target Service (core / ai / git / mcp)
    │
    ▼
CORSMiddleware
    │
    ▼
RequestLoggingMiddleware (timing, request ID)
    │
    ▼
Router (path matching)
    │
    ▼
Dependencies:
├── get_current_user
│     ├── Reads Bearer token from Authorization header
│     ├── Decodes JWT locally (HS256/RS256) using SECRET_KEY — NO HTTP call
│     ├── Checks token in Redis blacklist (for signed-out tokens)
│     └── Returns CurrentUser(id, email, full_name)
├── get_workspace_context
│     └── Queries workspace_members table via SQLAlchemy
└── rate_limit_api (Redis token-bucket)
    │
    ▼
Service Layer (business logic)
    │
    ▼
Repository Layer (SQLAlchemy async queries → PostgreSQL)
    │
    ▼
PostgreSQL 16 (Docker)
```

---

## Authentication & Authorization

> **No Supabase.** Auth is fully self-implemented using industry-standard JWT + bcrypt + Redis token revocation.

### Auth Flow

```
┌──────────┐  POST /api/auth/login    ┌─────────┐
│ Frontend │ ──────────────────────▶  │  core   │
│(authStore│                          │ :8000   │
│ Zustand) │ ◀────────────────────── │         │
│          │  {access_token,          │ 1. Query users table (email)
│          │   refresh_token,         │ 2. bcrypt.verify(password, hash)
│          │   user}                  │ 3. Generate access_token (JWT, 15min)
│          │                          │ 4. Generate refresh_token (JWT, 30d)
└──────────┘                          │ 5. Store refresh_token_hash in DB
 localStorage:                        │    + Redis (TTL 30d)
   access_token  (15 min)             └─────────┘
   refresh_token (30 days)

Subsequent requests:
┌──────────┐  GET /api/v1/...         ┌─────────────────────────┐
│ Frontend │  Authorization:          │  get_current_user dep   │
│          │  Bearer <access_token>   │  1. Decode JWT locally  │
│          │ ──────────────────────▶  │     (no HTTP call)      │
│          │                          │  2. Check Redis blacklist│
│          │ ◀──────────────────────  │     (revoked tokens)    │
└──────────┘  200 / 401               └─────────────────────────┘

Token refresh:
POST /api/auth/refresh  {refresh_token}
→ Validate refresh_token_hash in DB
→ Check not revoked in Redis
→ Issue new access_token (+ rotate refresh_token)
→ Revoke old refresh_token (hash added to Redis blacklist)

Sign out:
POST /api/auth/signout  {Authorization: Bearer ...}
→ Add access_token jti to Redis blacklist (TTL = remaining token lifetime)
→ Delete refresh_token from DB
```

### JWT Structure

```python
# Access Token payload (short-lived: 15 min)
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "jti": "unique-token-id",   # used for blacklisting on signout
  "type": "access",
  "iat": 1700000000,
  "exp": 1700000900
}

# Refresh Token payload (long-lived: 30 days)
{
  "sub": "user-uuid",
  "jti": "unique-token-id",
  "type": "refresh",
  "iat": 1700000000,
  "exp": 1702592000
}
```

### Auth Service Responsibilities (`auth_service.py`)

```
register(email, password, full_name)
  → hash password with bcrypt (cost=12)
  → insert user row
  → generate email verification token → store in email_verifications table
  → return tokens

login(email, password)
  → fetch user by email
  → bcrypt.verify(password, user.password_hash)
  → generate access_token + refresh_token
  → store refresh_token hash in refresh_tokens table
  → cache user session in Redis (optional)

refresh(refresh_token)
  → decode JWT, check type == "refresh"
  → verify hash exists in refresh_tokens table AND not expired
  → revoke old token, issue new pair (rotation)

signout(access_token, refresh_token)
  → add access_token jti to Redis blacklist
  → delete refresh_token from DB

verify_email(token)
  → look up email_verifications by token
  → mark user.is_verified = true
  → delete verification row
```

### Role Hierarchy

```
owner  → Full control (delete workspace, transfer ownership)
admin  → Manage members, invites, settings
member → CRUD projects, tasks, objectives
viewer → Read-only access
```

Role is checked in the **service layer** — never rely solely on URL guards.

---

## Redis Usage

Redis 7 runs as a Docker service. All services connect via `REDIS_URL=redis://redis:6379/0`.

| Purpose | Key Pattern | TTL | Notes |
|---------|------------|-----|-------|
| Token blacklist (signed-out access tokens) | `blacklist:jti:<jti>` | Remaining token lifetime | Set on signout |
| Refresh token revocation | `revoked:refresh:<jti>` | 30 days | Rotation guard |
| Rate limiter (token bucket) | `ratelimit:<ip>:<route>` | 60s | Sliding window |
| User session cache | `session:<user_id>` | 15 min | Optional: cache user row |
| Celery broker | `celery` default queue | — | Background tasks |
| Celery result backend | `celery-results` | 1 hour | Task result store |

### Redis Client (`shared/redis_client.py`)

```python
import aioredis
from functools import lru_cache

@lru_cache
def get_redis_settings() -> str:
    return settings.REDIS_URL  # redis://redis:6379/0

async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(get_redis_settings(), decode_responses=True)
```

---

## RAG Architecture

### Pipeline Overview

```
User Query
    │
    ▼
Query Classifier (pattern-based regex routing)
    │      │      │
    ▼      ▼      ▼
Vector  Keyword  Structured
Retriever Retriever Retriever
(pgvector) (ILIKE) (SQLAlchemy)
    │      │      │
    └──────┴──────┘
           │
           ▼
    RRF Reranker (k=60)
           │
    + Memory Loader
    (last 20 audit_log ai_chat events — SQLAlchemy query)
           │
           ▼
    Top-K Chunks → LLM Context
```

Embeddings are stored in `document_embeddings.embedding VECTOR(1536)` and queried via pgvector cosine similarity — previously done via Supabase RPC, now done via direct SQLAlchemy:

```python
# repositories/embedding_repo.py
async def match_documents(
    session: AsyncSession,
    query_embedding: list[float],
    workspace_id: UUID,
    match_count: int = 10,
) -> list[DocumentEmbedding]:
    return await session.execute(
        text("""
            SELECT *, 1 - (embedding <=> :embedding) AS similarity
            FROM document_embeddings
            WHERE workspace_id = :workspace_id
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """),
        {"embedding": query_embedding, "workspace_id": workspace_id, "limit": match_count}
    )
```

---

## Multi-Tenancy Model

All data is workspace-scoped. The **repository layer** always filters by `workspace_id`. There is no database-level RLS — isolation is enforced in application code.

```
Every repository method signature includes workspace_id:
  get_projects(workspace_id, user_id, ...) → only returns rows WHERE workspace_id = ?
  AND verifies user is a member of that workspace

Service layer verifies membership before any write operation.
```

```
┌─── Workspace A ────────────────────────┐
│  Owner: user_1                         │
│  Members: user_1(owner), user_2(admin) │
│                                        │
│  ┌── Project 1 ──┐  ┌── Project 2 ──┐ │
│  │ Tasks         │  │ Tasks         │ │
│  │ Objectives    │  │ Objectives    │ │
│  │ Timeline      │  │ Timeline      │ │
│  │ Costs         │  │ Costs         │ │
│  │ Git Repos     │  │ Git Repos     │ │
│  └───────────────┘  └───────────────┘ │
│  Git Accounts (shared)                 │
│  AI Models (shared)                    │
│  Notifications (per-user)              │
│  Audit Log (workspace-wide)            │
└────────────────────────────────────────┘
```

---

## Deployment

### Docker Compose (Production & Development)

```yaml
# docker-compose.yml (simplified view)
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: oppm
      POSTGRES_USER: oppm
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

  gateway:
    build: ./services/gateway
    ports: ["8080:8080"]
    environment:
      CORE_URLS: http://core:8000
      AI_URLS: http://ai:8001
      GIT_URLS: http://git:8002
      MCP_URLS: http://mcp:8003

  core:
    build: ./services/core
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://oppm:${DB_PASSWORD}@postgres:5432/oppm
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      JWT_ALGORITHM: HS256
      ACCESS_TOKEN_EXPIRE_MINUTES: 15
      REFRESH_TOKEN_EXPIRE_DAYS: 30

  ai:
    build: ./services/ai
    ports: ["8001:8001"]
    depends_on: [postgres, redis]

  git:
    build: ./services/git
    ports: ["8002:8002"]
    depends_on: [postgres]

  mcp:
    build: ./services/mcp
    ports: ["8003:8003"]
    depends_on: [postgres]

  frontend:
    build: ./frontend
    ports: ["5173:5173"]

volumes:
  postgres_data:
  redis_data:
```

### Starting Services

```bash
# Production
docker compose up -d

# Development with hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Run migrations after first start
docker compose exec core alembic upgrade head
```

### Native Development (no Docker — services only)

Start PostgreSQL and Redis via Docker, run Python services natively:

```bash
# Infrastructure only
docker compose up postgres redis -d

# Terminal 1 — gateway
./services/gateway/start.ps1    # port 8080

# Terminals 2–5
./services/core/start.ps1       # port 8000
./services/ai/start.ps1         # port 8001
./services/git/start.ps1        # port 8002
./services/mcp/start.ps1        # port 8003

# Terminal 6
cd frontend && npm run dev       # port 5173
```

---

## Environment Variables

### `services/shared` / all services reference these

```dotenv
# ── Database ────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://oppm:password@localhost:5432/oppm

# ── Redis ───────────────────────────────────────────────
REDIS_URL=redis://:password@localhost:6379/0

# ── JWT Auth (NO Supabase) ──────────────────────────────
JWT_SECRET_KEY=your-256-bit-secret-here          # generate: openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# ── CORS ────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ── AI / LLM (optional — only needed in ai service) ─────
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_URL=http://localhost:11434

# ── Service URLs (gateway only) ─────────────────────────
CORE_URLS=http://localhost:8000
AI_URLS=http://localhost:8001
GIT_URLS=http://localhost:8002
MCP_URLS=http://localhost:8003
```

> ⚠️ **Removed variables** (no longer needed anywhere):
> - `SUPABASE_URL`
> - `SUPABASE_ANON_KEY`
> - `SUPABASE_SERVICE_ROLE_KEY`
> - `NEXT_PUBLIC_SUPABASE_URL`
> - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

---

## Migration from Supabase

### What changes

| Before (Supabase) | After (Self-hosted) |
|---|---|
| `supabase.auth.get_user(token)` | `jwt.decode(token, SECRET_KEY)` |
| `supabase.auth.sign_in_with_password()` | `auth_service.login()` |
| `supabase.auth.refresh_session()` | `auth_service.refresh()` |
| `SupabaseClient.table("x").select()` | `SQLAlchemy session.execute(select(X))` |
| Supabase RLS policies | `workspace_id` filter in repositories |
| `match_documents()` Supabase RPC | Direct pgvector SQL via SQLAlchemy |
| Supabase hosted PostgreSQL | `pgvector/pgvector:pg16` Docker image |
| In-memory rate limiter fallback | Redis rate limiter (always available) |
| Supabase Storage | Local volume / S3-compatible (future) |

### Migration Steps

1. Run `alembic revision --autogenerate` to create initial migration from SQLAlchemy models
2. Run `alembic upgrade head` to apply schema to PostgreSQL
3. Replace all `shared/database.py` (Supabase client) with SQLAlchemy engine/session
4. Replace all `shared/auth.py` (Supabase `get_user()`) with local JWT decode
5. Replace all repositories (`.table().select()` → SQLAlchemy ORM queries)
6. Remove `supabase` and `supabase-py` from all `requirements.txt`
7. Add `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `aioredis`, `bcrypt`, `python-jose` to `requirements.txt`
8. Remove all Supabase env vars from `.env` files
9. Update frontend `lib/api.ts` — ensure no Supabase JS client remains

---

## AI Agent Configuration

```
.claude/
├── rules/
│   ├── api-conventions.md      # API route & naming conventions
│   ├── code-style.md           # Python & TypeScript style rules
│   ├── database.md             # SQLAlchemy patterns, NO Supabase
│   ├── auth.md                 # JWT + bcrypt + Redis token rules
│   ├── error-handling.md       # Error response patterns
│   ├── project-structure.md    # Layer boundaries
│   ├── security.md             # Auth & data access security
│   └── testing.md              # Test patterns
└── commands/
    ├── deploy.md
    ├── fix-issue.md
    └── review.md
```

**Critical rules for AI agents:**
- Never import or reference `supabase`, `supabase-py`, or `gotrue`
- Always use `AsyncSession` from SQLAlchemy for database access
- Always filter queries by `workspace_id`
- JWT validation is **always local** — never an external HTTP call
- Redis is **always available** (Docker) — no in-memory fallback needed
- Password hashing uses `bcrypt` with `rounds=12`
- Refresh tokens are **rotated** on every use (one-time use)