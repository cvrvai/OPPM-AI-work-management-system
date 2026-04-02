# OPPM AI Work Management System — Architecture

> Multi-tenant, workspace-scoped AI-powered project management platform following the **One Page Project Manager (OPPM)** methodology.

## Table of Contents
- [System Overview](#system-overview)
- [Architecture Layers](#architecture-layers)
- [Database Design](#database-design)
- [Backend Architecture](#backend-architecture)
- [Frontend Architecture](#frontend-architecture)
- [API Design](#api-design)
- [RAG Architecture](#rag-architecture)
- [Authentication & Authorization](#authentication--authorization)
- [Multi-Tenancy Model](#multi-tenancy-model)
- [Deployment](#deployment)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        OPPM AI System                           │
│                                                                  │
│  ┌─────────┐     ┌─────────────┐     ┌────────────────────────┐ │
│  │ React   │────▶│ FastAPI     │────▶│ Supabase PostgreSQL   │ │
│  │ Frontend│◀────│ Backend     │◀────│ + RLS + Auth          │ │
│  │ (SPA)   │     │ (REST API)  │     │                        │ │
│  └─────────┘     └──────┬──────┘     └────────────────────────┘ │
│                         │                                        │
│                  ┌──────▼──────┐                                 │
│                  │ AI Providers│                                  │
│                  │ Ollama/GPT/ │                                  │
│                  │ Claude/Kimi │                                  │
│                  └─────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Architecture Layers

### Backend (4-Layer Clean Architecture)

```
┌───────────────────────────────────────────────────┐
│  Routers (API Layer)                              │
│  routers/v1/*.py — HTTP handlers, validation      │
├───────────────────────────────────────────────────┤
│  Services (Business Logic)                        │
│  services/*.py — orchestration, rules, workflows  │
├───────────────────────────────────────────────────┤
│  Repositories (Data Access)                       │
│  repositories/*.py — Supabase queries, CRUD       │
├───────────────────────────────────────────────────┤
│  Infrastructure (External)                        │
│  infrastructure/llm/*.py — AI model adapters      │
│  middleware/*.py — auth, rate limiting, logging    │
└───────────────────────────────────────────────────┘
```

### Frontend (Feature-Module Pattern)

```
src/
├── components/        # Shared UI components
│   ├── layout/        # Header, Sidebar, Layout
│   └── workspace/     # Workspace selector
├── hooks/             # Shared custom hooks
├── lib/               # API client, Supabase, utils
├── pages/             # Route-level page components
├── stores/            # Zustand stores (auth, workspace)
└── types/             # TypeScript interfaces
```

---

## Database Design

### Entity Relationship Diagram

```
                    ┌────────────────┐
                    │   workspaces   │
                    │────────────────│
                    │ id (PK)        │
                    │ name           │
                    │ slug (unique)  │
                    │ description    │
                    │ created_by     │
                    └───────┬────────┘
                            │ 1:N
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
  ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
  │workspace_members │ │workspace_    │ │  projects        │
  │──────────────────│ │  invites     │ │──────────────────│
  │ id (PK)          │ │──────────────│ │ id (PK)          │
  │ workspace_id(FK) │ │ id (PK)      │ │ workspace_id(FK) │
  │ user_id          │ │workspace_id  │ │ title            │
  │ role             │ │ email        │ │ status           │
  │  (owner/admin/   │ │ role         │ │ priority         │
  │   member/viewer) │ │ token        │ │ progress         │
  └────────┬─────────┘ │ expires_at   │ │ lead_id (FK)     │
           │            └──────────────┘ └───────┬──────────┘
           │                                     │ 1:N
     ┌─────┴────────────────┬───────────────┬────┴──────────┐
     ▼                      ▼               ▼               ▼
┌──────────────┐  ┌───────────────┐  ┌──────────────┐ ┌──────────────┐
│project_      │  │oppm_objectives│  │   tasks      │ │project_costs │
│  members     │  │───────────────│  │──────────────│ │──────────────│
│──────────────│  │ id (PK)       │  │ id (PK)      │ │ id (PK)      │
│ id (PK)      │  │ project_id(FK)│  │ project_id   │ │ project_id   │
│ project_id   │  │ title         │  │ title        │ │ category     │
│workspace_    │  │ owner_id      │  │ status       │ │planned_amount│
│  member_id   │  │ sort_order    │  │ progress     │ │actual_amount │
│ role         │  └───────┬───────┘  │ assignee_id  │ └──────────────┘
└──────────────┘          │          │oppm_objective │
                          │          │  _id (FK)     │
                    ┌─────▼────────┐ └──────┬───────┘
                    │oppm_timeline │        │
                    │  _entries    │  ┌─────▼────────┐
                    │──────────────│  │task_assignees │
                    │ id (PK)      │  │──────────────│
                    │ objective_id │  │ task_id       │
                    │ year, month  │  │workspace_     │
                    │ status       │  │  member_id    │
                    └──────────────┘  └──────────────┘
```

### Additional Tables

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
│  commit_analyses   │                                 │
│────────────────────│◀────────────────────────────────┘
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
│ is_read            │  │  openai/kimi/   │  │ old_data          │
│ link               │  │  custom)        │  │ new_data          │
│ metadata           │  │ model_id        │  │ ip_address        │
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
│ embedding VECTOR(1536)        │
└───────────────────────────────┘

Searchable via `match_documents(query_embedding, match_count, filter_workspace_id)` pgvector RPC (cosine similarity).
```

### Row-Level Security (RLS)

All tables have RLS enabled with workspace-scoped policies:
- **Helper functions**: `is_workspace_member(ws_id)`, `is_workspace_admin(ws_id)`
- **Read**: User must be a member of the workspace owning the data
- **Write**: User must be member/admin/owner depending on role requirements

---

## Backend Architecture

### Directory Structure

```
backend/
├── main.py                    # App factory + middleware chain
├── config.py                  # Pydantic settings (env vars)
├── database.py                # Supabase client singleton
├── middleware/
│   ├── auth.py                # Supabase auth.get_user() → CurrentUser
│   ├── workspace.py           # Workspace membership → WorkspaceContext
│   ├── rate_limit.py          # Token bucket rate limiter
│   └── logging.py             # Request logging + timing
├── repositories/
│   ├── base.py                # BaseRepository (generic CRUD)
│   ├── workspace_repo.py      # Workspace + Member + Invite repos
│   ├── project_repo.py        # Project + ProjectMember repos
│   ├── task_repo.py           # Task repo (with progress calc)
│   ├── oppm_repo.py           # Objective + Timeline + Cost repos
│   ├── git_repo.py            # GitAccount + Repo + Commit repos
│   └── notification_repo.py   # Notification + Audit repos
├── services/
│   ├── workspace_service.py   # Workspace lifecycle + invites
│   ├── project_service.py     # Project CRUD + members
│   ├── task_service.py        # Task CRUD + progress recalc
│   ├── oppm_service.py        # OPPM objectives, timeline, costs
│   ├── git_service.py         # Git integration + webhooks
│   ├── notification_service.py # Notification CRUD
│   ├── dashboard_service.py   # Aggregated stats
│   ├── ai_analyzer.py         # AI commit analysis (with LLM fallback)
│   ├── ai_chat_service.py     # AI chat + suggest-plan + weekly summary
│   └── rag_service.py         # RAG pipeline orchestration
├── routers/
│   ├── v1/                    # New workspace-scoped routes
│   │   ├── auth.py            # GET /me
│   │   ├── workspaces.py      # Workspace CRUD + members + invites
│   │   ├── projects.py        # Workspace-scoped project CRUD
│   │   ├── tasks.py           # Workspace-scoped task CRUD
│   │   ├── oppm.py            # Objectives + timeline + costs
│   │   ├── git.py             # Git accounts + repos + commits + webhook
│   │   ├── ai.py              # AI model config (ALLOWED_PROVIDERS validation)
│   │   ├── ai_chat.py         # AI chat, suggest-plan, weekly-summary
│   │   ├── rag.py             # RAG query endpoint
│   │   ├── mcp.py             # MCP tool list + execution
│   │   ├── notifications.py   # User-scoped notifications
│   │   └── dashboard.py       # Workspace stats
│   └── *.py                   # Legacy routes (backwards compat)
├── schemas/
│   ├── common.py              # Enums, PaginatedResponse, errors
│   ├── workspace.py           # Workspace CRUD schemas
│   ├── project.py             # Project CRUD schemas
│   ├── task.py                # Task CRUD schemas
│   ├── oppm.py                # OPPM objective/timeline/cost
│   ├── git.py                 # Git account/repo schemas
│   ├── ai.py                  # AI model config schemas
│   ├── ai_chat.py             # Chat request/response schemas
│   ├── rag.py                 # RAGQueryRequest/Response
│   ├── notification.py        # Notification schemas
│   └── dashboard.py           # Dashboard stats schema
└── infrastructure/
    ├── llm/
    │   ├── base.py            # LLMAdapter ABC + ProviderUnavailableError
    │   ├── __init__.py        # call_with_fallback() factory
    │   ├── ollama.py          # Ollama local/cloud adapter
    │   ├── kimi.py            # Kimi/Moonshot adapter
    │   ├── anthropic.py       # Claude adapter
    │   └── openai.py          # OpenAI adapter
    ├── rag/
    │   ├── __init__.py        # Package exports
    │   ├── embedder.py        # OpenAI text-embedding-3-small (1536 dims)
    │   ├── reranker.py        # Reciprocal Rank Fusion (RRF)
    │   ├── memory.py          # Conversation memory from audit_log
    │   ├── agent.py           # Pattern-based query classifier
    │   └── retrievers/
    │       ├── base_retriever.py    # RetrievedChunk dataclass + ABC
    │       ├── vector_retriever.py  # pgvector cosine similarity
    │       ├── keyword_retriever.py # ILIKE on tasks/objectives
    │       └── structured_retriever.py  # Direct DB for costs/projects
    └── mcp/
        ├── __init__.py        # Package exports
        └── tools/
            ├── __init__.py    # TOOL_REGISTRY dict
            ├── project_tools.py   # get_project_status, list_projects
            ├── objective_tools.py # list_at_risk_objectives
            ├── task_tools.py      # get_task_summary
            └── commit_tools.py    # summarize_recent_commits
```

### Request Flow

```
Client Request
    │
    ▼
Vite Dev Proxy (/api → localhost:8000, dev only)
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
├── get_current_user (validates JWT via supabase.auth.get_user())
├── get_workspace_context (membership check)
├── rate_limit_api / rate_limit_webhook
    │
    ▼
Service Layer (business logic)
    │
    ▼
Repository Layer (data access)
    │
    ▼
Supabase Client (service_role_key, bypasses RLS) → PostgreSQL
```

---

## API Design

### V1 Endpoints (Workspace-Scoped)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/auth/me` | JWT | Current user info |
| `GET` | `/api/v1/workspaces` | JWT | List user's workspaces |
| `POST` | `/api/v1/workspaces` | JWT | Create workspace |
| `PUT` | `/api/v1/workspaces/:ws` | Admin | Update workspace |
| `DELETE` | `/api/v1/workspaces/:ws` | Admin | Delete workspace |
| `GET` | `/api/v1/workspaces/:ws/members` | Member | List members |
| `PUT` | `/api/v1/workspaces/:ws/members/:id` | Admin | Update member role |
| `DELETE` | `/api/v1/workspaces/:ws/members/:id` | Admin | Remove member |
| `POST` | `/api/v1/workspaces/:ws/invites` | Admin | Create invite |
| `POST` | `/api/v1/invites/accept` | JWT | Accept invite by token |
| `GET` | `/api/v1/workspaces/:ws/projects` | Member | List projects (paginated) |
| `POST` | `/api/v1/workspaces/:ws/projects` | Writer | Create project |
| `GET` | `/api/v1/workspaces/:ws/projects/:id` | Member | Get project |
| `PUT` | `/api/v1/workspaces/:ws/projects/:id` | Writer | Update project |
| `DELETE` | `/api/v1/workspaces/:ws/projects/:id` | Writer | Delete project |
| `GET` | `/api/v1/workspaces/:ws/tasks` | Member | List tasks |
| `POST` | `/api/v1/workspaces/:ws/tasks` | Writer | Create task |
| `PUT` | `/api/v1/workspaces/:ws/tasks/:id` | Writer | Update task |
| `DELETE` | `/api/v1/workspaces/:ws/tasks/:id` | Writer | Delete task |
| `GET` | `/api/v1/workspaces/:ws/projects/:id/oppm/objectives` | Member | OPPM objectives |
| `POST` | `/api/v1/workspaces/:ws/projects/:id/oppm/objectives` | Writer | Create objective |
| `GET` | `/api/v1/workspaces/:ws/projects/:id/oppm/timeline` | Member | Timeline entries |
| `GET` | `/api/v1/workspaces/:ws/projects/:id/oppm/costs` | Member | Project costs |
| `GET` | `/api/v1/workspaces/:ws/commits` | Member | Commit list |
| `GET` | `/api/v1/workspaces/:ws/github-accounts` | Member | Git accounts |
| `POST` | `/api/v1/workspaces/:ws/github-accounts` | Admin | Add git account |
| `GET` | `/api/v1/workspaces/:ws/ai/models` | Member | AI models |
| `POST` | `/api/v1/workspaces/:ws/ai/models` | Admin | Add AI model |
| `POST` | `/api/v1/workspaces/:ws/projects/:id/ai/chat` | Member | AI chat |
| `POST` | `/api/v1/workspaces/:ws/projects/:id/ai/suggest-plan` | Member | Suggest OPPM plan |
| `GET` | `/api/v1/workspaces/:ws/projects/:id/ai/weekly-summary` | Member | Weekly AI summary |
| `POST` | `/api/v1/workspaces/:ws/rag/query` | Member | RAG retrieval pipeline |
| `GET` | `/api/v1/workspaces/:ws/mcp/tools` | Member | List MCP tools |
| `POST` | `/api/v1/workspaces/:ws/mcp/call` | Member | Execute MCP tool |
| `GET` | `/api/v1/workspaces/:ws/dashboard/stats` | Member | Dashboard stats |
| `GET` | `/api/v1/notifications` | JWT | User notifications |
| `PUT` | `/api/v1/notifications/read-all` | JWT | Mark all read |
| `POST` | `/api/v1/git/webhook` | HMAC | GitHub webhook |

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
 (pgvector) (ILIKE) (direct DB)
    │      │      │
    └──────┴──────┘
           │
           ▼
    RRF Reranker (k=60)
           │
    + Memory Loader
    (last 20 audit_log ai_chat events)
           │
           ▼
    Top-K Chunks → LLM Context
```

### Query Routing

| Query Pattern | Retrievers Used |
|---------------|-----------------|
| objective / goal | vector + keyword |
| task / todo | vector + keyword |
| commit / push | vector only |
| cost / budget | structured only |
| status / progress | vector + structured |
| team / member | structured + vector |
| timeline | vector + structured |
| (default) | all three |

### LLM Fallback Chain

```
call_with_fallback(models=[model1, model2, ...], prompt)
    │
    ├── Try model1.call() → success → return
    │
    ├── ProviderUnavailableError → log warning → continue
    │
    ├── Try model2.call() → success → return
    │
    └── All failed → raise ProviderUnavailableError
```

All LLM adapters raise `ProviderUnavailableError` on:
- `httpx.ConnectError` (service unreachable)
- `httpx.TimeoutException`
- `httpx.HTTPStatusError` with 404 / 502 / 503 / 529

---

## Authentication & Authorization

### Auth Flow
```
┌──────────┐    ┌──────────────┐    ┌───────────┐
│  Client  │───▶│ Supabase Auth│───▶│ JWT Token │
│  (Login) │◀───│ (email/pass) │◀───│ (returned)│
└──────────┘    └──────────────┘    └─────┬─────┘
                                          │
                              ┌───────────▼─────────────┐
                              │ Backend: get_current_user│
                              │ db.auth.get_user(token)  │
                              │ (validates via Supabase  │
                              │  Auth API, NOT local JWT)│
                              └───────────┬─────────────┘
                                          │
                              ┌───────────▼─────────────┐
                              │  get_workspace_context   │
                              │  (checks workspace_     │
                              │   members table for role)│
                              └──────────────────────────┘
```

### Role Hierarchy
```
owner  → Full control (can delete workspace, transfer ownership)
admin  → Manage members, invites, settings
member → CRUD projects, tasks, objectives
viewer → Read-only access
```

---

## Multi-Tenancy Model

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
│                                        │
│  Git Accounts (shared)                 │
│  AI Models (shared)                    │
│  Notifications (per-user)              │
│  Audit Log (workspace-wide)            │
└────────────────────────────────────────┘

┌─── Workspace B ────────────────────────┐
│  Owner: user_2                         │
│  Members: user_2(owner), user_3(member)│
│  ... (completely isolated data) ...    │
└────────────────────────────────────────┘
```

All data queries include `workspace_id` filtering. RLS policies enforce at the database level.

---

## Deployment

### Docker Compose

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env

  frontend:
    build: ./frontend
    ports: ["5173:80"]
    depends_on: [backend]
```

### Scaling Considerations (100k Users)

| Component | Current | Production |
|-----------|---------|------------|
| Rate Limiter | In-memory token bucket | Redis-backed |
| Database | Supabase hosted | Supabase Pro + connection pooler |
| Sessions | JWT (stateless) | JWT (stateless) ✓ |
| File Storage | N/A | Supabase Storage |
| Background Jobs | In-process | Celery + Redis |
| Caching | None | Redis cache layer |
| Search | SQL LIKE | pg_trgm + full-text search |

---

## AI Agent Configuration

Project uses `.claude/` directory for AI agent rules and commands:

```
.claude/
├── rules/                      # Mandatory rules for all agents
│   ├── api-conventions.md     # API route & naming conventions
│   ├── code-style.md          # Python & TypeScript style rules
│   ├── database.md            # Schema design & RLS rules
│   ├── error-handling.md      # Error response patterns
│   ├── project-structure.md   # Layer boundaries
│   ├── security.md            # Auth & data access security
│   └── testing.md             # Test patterns & checklist
└── commands/                   # Reusable agent workflows
    ├── deploy.md              # Deployment checklist
    ├── fix-issue.md           # Issue diagnosis workflow
    └── review.md              # Code review checklist
```

See `CLAUDE.md` at project root for the agent entry point.
