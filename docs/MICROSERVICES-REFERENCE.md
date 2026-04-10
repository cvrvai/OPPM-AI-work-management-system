# Microservices Reference

Last updated: 2026-04-09

## Purpose

This document explains what each backend service owns, how requests are routed, and which folders you should open first when implementing backend features.

It is the folder-level reference for the current microservices layout.

## Active Service Map

The backend is split into five active runtime areas plus one shared package:

- `services/core/`
- `services/ai/`
- `services/git/`
- `services/mcp/`
- `services/gateway/`
- `shared/`

There is also a Docker nginx gateway in `gateway/`.

## Runtime Ports

Typical native development ports:

| Component | Port | Purpose |
|---|---|---|
| frontend | `5173` | React dev server |
| python gateway | `8080` | Native reverse proxy and load balancer |
| core | `8000` | Auth and core business APIs |
| ai | `8001` | AI, RAG, chat, summaries |
| git | `8002` | GitHub and commit analysis ingestion |
| mcp | `8003` | MCP tool listing and execution |

## Request Routing

Public requests go to the gateway first.

Current routing summary:

- AI routes -> `services/ai/`
- Git routes -> `services/git/`
- MCP routes -> `services/mcp/`
- all remaining `/api/*` routes -> `services/core/`

The same routing intent must exist in both:

- `services/gateway/main.py`
- `gateway/nginx.conf`

## Shared Package Boundary

`shared/` is the critical backend boundary.

It contains:

- `database.py`
  SQLAlchemy base, async engine, session lifecycle.
- `auth.py`
  JWT validation, workspace authorization, internal API key validation.
- `redis_client.py`
  Redis bootstrap and helper access.
- `models/`
  Shared ORM models used by all services.
- `schemas/`
  Common shared enums and response wrappers.
- `config.py`
  Shared settings used across services.

When a new feature needs a table or shared ORM change, it belongs in `shared/models/` and its migration belongs in the core service migration chain.

## Folder Guide By Service

### `services/core/`

Primary business service.

Important folders:

- `main.py`
  FastAPI app factory, middleware setup, route mounting, health endpoint.
- `routers/`
  Public HTTP endpoints. `routers/auth.py` owns `/api/auth/*`. `routers/v1/` owns workspace and user-scoped APIs.
- `schemas/`
  Pydantic request and response contracts for core routes.
- `services/`
  Business logic layer for workspaces, projects, tasks, OPPM, notifications, auth.
- `repositories/`
  SQLAlchemy persistence layer.
- `middleware/`
  Request logging and other service-local middleware.
- `alembic/`
  Database migration history.
- `tests/`
  Current backend tests for core behavior.

Current functional ownership:

- auth
- workspaces
- members and invites
- member skills
- projects and project members
- tasks, task reports, and task dependencies
- task permission enforcement (lead-only create, assignee-only report, lead-only approve)
- OPPM objectives (with A/B/C priority), timeline, costs
- notifications
- dashboard stats

Start here when changing:

- CRUD behavior
- authorization rules
- workspace-scoped business logic
- migrations

### `services/ai/`

AI and retrieval service.

Important folders:

- `main.py`
  App factory and route registration.
- `routers/v1/`
  AI model config, chat, plan suggestion, reindex, RAG endpoint, feedback routes.
- `routers/internal.py`
  Internal commit-analysis endpoint protected by `X-Internal-API-Key`.
- `services/`
  Chat, analyzer, RAG orchestration, indexing logic.
- `repositories/`
  Data access for AI flows. `oppm_repo.py` owns all OPPM-domain reads used by tools.
- `infrastructure/rag/`
  RAG pipeline components:
  - `agent_loop.py` — multi-turn TAOR tool execution loop (max 7 iterations, low-confidence requery, final wrap-up fallback)
  - `query_rewriter.py` — LLM-based query expansion before retrieval
  - `guardrails.py` — input injection detection and output sensitive-data scrub
  - `semantic_cache.py` — Redis embedding cache (cosine ≥ 0.92, TTL 300 s)
  - `agent.py`, `retrievers/`, `reranker.py` — classifier and retrieval stages
- `infrastructure/tools/`
  AI-callable tool registry:
  - `registry.py` — global `ToolRegistry` singleton with `register`, `execute`, and schema methods
  - `base.py` — `ToolDefinition`, `ToolParam`, `ToolResult` data classes
  - `oppm_tools.py` — 5 OPPM tools (create/update/delete objectives, set timeline status)
  - `task_tools.py` — 5 task tools (create/update/delete/assign/dependency)
  - `cost_tools.py` — 5 cost tools (costs, risks, deliverables, project update)
  - `read_tools.py` — 6 read tools (summary, task details, search, risks, costs, team workload)
  - `project_tools.py` — 3 workspace/project tools (create, list, update projects)
- `infrastructure/llm/`
  LLM adapter layer:
  - `base.py` — `LLMAdapter` with `call_with_tools()` default
  - `openai.py`, `anthropic.py` — native tool-calling implementations
  - `ollama.py`, `kimi.py` — XML-prompt-based tool calling
  - `tool_parser.py` — unified parser for native and XML tool-call formats
- `schemas/`
  AI request and response contracts. `ChatResponse` includes `iterations: int` and `updated_entities`.

Current functional ownership:

- workspace AI chat with RAG plus workspace-scoped tool execution for write-capable callers
- project AI chat with bounded TAOR tool loop (up to 7 iterations)
- input guardrails and output guardrails
- LLM query rewriting
- semantic cache (Redis-backed)
- tool registry with 24 tools (oppm × 5, task × 5, cost × 5, read × 6, project × 3)
- native LLM function calling for OpenAI and Anthropic
- XML-prompt tool calling for Ollama and Kimi
- weekly summary
- AI plan suggestion and commit
- AI model configuration
- file parsing, OPPM fill, and OPPM image extraction
- workspace reindexing
- RAG retrieval
- user feedback (logged to `audit_log`)
- internal analyze-commits endpoint

Architectural note:

- the AI service also writes shared business data through its own tool handlers and repositories; the service boundary is at the HTTP/router layer, not at the database level

Start here when changing:

- LLM provider support
- retrieval pipeline behavior
- prompt orchestration
- tool addition or parameter changes
- AI response shapes

### `services/git/`

GitHub integration service.

Important folders:

- `main.py`
  App bootstrap.
- `routers/v1/`
  GitHub account, repo, commit, report, webhook routes.
- `services/`
  GitHub service logic and webhook processing.
- `repositories/`
  Repo config, commit, and analysis persistence.
- `schemas/`
  GitHub account and repo config contracts.

Current functional ownership:

- GitHub account registration
- repository configuration per project
- webhook validation
- commit storage
- developer reports
- recent analysis retrieval
- triggering internal AI analysis

Start here when changing:

- GitHub account flows
- webhook validation
- commit ingestion
- cross-service handoff to AI

### `services/mcp/`

HTTP wrapper around workspace-scoped MCP tools.

Important folders:

- `main.py`
  App bootstrap.
- `routers/v1/`
  Tool list and tool call routes.
- `infrastructure/mcp/tools/`
  Actual callable tool implementations and registry.

Current functional ownership:

- tool discovery
- tool execution scoped to workspace
- exposing structured tool contracts to AI integrations

Start here when changing:

- tool registry
- tool parameter contracts
- workspace-aware tool logic

### `services/gateway/`

Python gateway used for native development.

Important files:

- `main.py`
  Route matching, proxying, CORS, upstream forwarding.
- `load_balancer.py`
  Health-aware round robin selection.
- `config.py`
  Upstream service URLs and runtime settings.

Current responsibilities:

- route matching by URL pattern
- service health-aware forwarding
- response header preservation
- service availability handling for local development

Start here when changing:

- service route ownership
- local development proxy behavior
- load balancing behavior

### `gateway/`

Container-facing nginx gateway.

Important file:

- `nginx.conf`
  Production and Docker routing rules.

Treat this folder as the deployment twin of `services/gateway/`. If one route table changes, the other must change too.

## Cross-Service Flows

### Auth And Standard CRUD

- frontend -> gateway -> core -> shared database

### GitHub Analysis

- GitHub -> git service webhook -> commit storage -> AI internal analysis -> persisted analyses

### AI Chat And RAG

- frontend -> gateway -> AI service -> shared database and embeddings -> model provider

### MCP Tool Execution

- frontend or model integration -> gateway -> MCP service -> workspace tool implementation -> shared database

## Layering Rules

The main backend layering pattern is:

```text
router -> service -> repository -> shared database session
```

Notes:

- routers own HTTP concerns
- services own business rules
- repositories own query patterns
- `shared/` owns cross-service contracts and data models

## Feature Lookup Table

| Feature | First place to look |
|---|---|
| Login, signup, refresh | `services/core/routers/auth.py`, `services/core/services/auth_service.py` |
| Workspace membership and invites | `services/core/routers/v1/workspaces.py`, `services/core/services/workspace_service.py` |
| Project CRUD | `services/core/routers/v1/projects.py`, `services/core/services/project_service.py` |
| Task CRUD and reports | `services/core/routers/v1/tasks.py`, `services/core/services/task_service.py` |
| OPPM board | `services/core/routers/v1/oppm.py`, `services/core/services/oppm_service.py` |
| Notifications | `services/core/routers/v1/notifications.py`, `services/core/services/notification_service.py` |
| Dashboard | `services/core/routers/v1/dashboard.py`, `services/core/services/dashboard_service.py` |
| AI model settings | `services/ai/routers/v1/ai.py` |
| Chat and weekly summary | `services/ai/routers/v1/ai_chat.py`, `services/ai/services/ai_chat_service.py` |
| RAG query | `services/ai/routers/v1/rag.py`, `services/ai/services/rag_service.py` |
| GitHub webhook | `services/git/routers/v1/git.py`, `services/git/services/git_service.py` |
| MCP tools | `services/mcp/routers/v1/mcp.py`, `services/mcp/infrastructure/mcp/tools/` |

## Current Contract And Architecture Caveats

These are the most important real-world quirks to keep in mind:

- the backend currently uses local HS256 JWT validation in `shared/auth.py`
- workspace membership is the core authorization join, not direct user ownership
- project member add requests use a public field named `user_id`, but the stored relation is a workspace member id
- workspace responses expose `current_user_role`, while some frontend types still expect `role`
- both Python gateway and nginx gateway need to stay aligned manually
- the task domain still has both `assignee_id` and `task_assignees`, but the live flow uses `assignee_id`

## Recommended Change Checklist

When adding backend functionality:

1. decide which service owns the feature
2. add or update shared models if data changes are cross-service
3. add migration in `services/core/alembic/`
4. add schema in the owning service
5. add repository logic if persistence changes
6. add service logic
7. add route wiring
8. update [API-REFERENCE.md](API-REFERENCE.md), [ERD.md](ERD.md), and [TESTING-GUIDE.md](TESTING-GUIDE.md)
