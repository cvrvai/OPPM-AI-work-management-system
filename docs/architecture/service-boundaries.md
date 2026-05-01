# Microservices Reference

Last updated: 2026-05-01

## Purpose

This document explains what each backend service owns, how requests are routed, and which folders you should open first when implementing backend features.

It is the folder-level reference for the current microservices layout.

For service-by-service feature inventories and upgrade impact guidance, use [services/README.md](services/README.md).
For database-by-service ownership and touchpoints, use [database/README.md](database/README.md).

For runtime diagrams, use [FLOWCHARTS.md](flowcharts.md):

- Service interaction map: **S1-S3**
- Function-level service flows: **14-17**

## Active Service Map

The backend is split into four active runtime services plus one shared package:

- `services/workspace/`
- `services/intelligence/`
- `services/integrations/`
- `services/automation/`
- `services/gateway/`
- `shared/`

There is also a Docker nginx gateway in `gateway/`.

## Runtime Ports

Typical native development ports:

| Component | Port | Purpose |
|---|---|---|
| frontend | `5173` | React dev server |
| python gateway | `8080` | Native reverse proxy and load balancer |
| workspace | `8000` | Auth and core business APIs |
| intelligence | `8001` | LLM, RAG, chat, summaries |
| integrations | `8002` | GitHub and commit analysis ingestion |
| automation | `8003` | MCP tool listing and execution |

## Request Routing

Public requests go to the gateway first.

Current routing summary:

- Intelligence routes -> `services/intelligence/`
- Integration routes -> `services/integrations/`
- Automation routes -> `services/automation/`
- `/internal/analyze-commits` -> `services/intelligence/` (internal service-to-service path)
- all remaining `/api/*` routes -> `services/workspace/`

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

When a new feature needs a table or shared ORM change, it belongs in `shared/models/` and its migration belongs in the workspace service migration chain.

## Folder Guide By Service

### `services/workspace/`

Primary business service (modular monolith with DDD domains).

Important folders:

- `main.py`
  FastAPI app factory, middleware setup, route mounting, health endpoint.
- `domains/`
  Business modules organized by domain:
  - `domains/auth/` — login, signup, refresh, profile
  - `domains/workspace/` — workspace CRUD, members, invites, skills
  - `domains/project/` — project CRUD, project members
  - `domains/task/` — task CRUD, reports, dependencies
  - `domains/oppm/` — objectives, timeline, costs, deliverables
  - `domains/notification/` — notifications, audit log
  - `domains/dashboard/` — aggregated workspace stats
  - `domains/agile/` — epics, user stories, sprints
  - `domains/waterfall/` — phases, phase documents
- `infrastructure/`
  External clients (email, Google Sheets, export).
- `middleware/`
  Request logging and other service-local middleware.
- `alembic/`
  Database migration history.
- `tests/`
  Current backend tests for core behavior.
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
- agile workflows (epics, user stories, sprints, retrospective)
- waterfall workflows (phases and phase documents)
- notifications
- dashboard stats

Start here when changing:

- CRUD behavior
- authorization rules
- workspace-scoped business logic
- migrations

### `services/intelligence/`

AI and retrieval service.

Important folders:

- `main.py`
  App factory and route registration.
- `domains/`
  - `domains/chat/` — workspace/project chat, feedback
  - `domains/rag/` — retrieval, reindexing, semantic cache
  - `domains/analysis/` — commit analysis, OCR fill, OPPM fill, plan suggestion
  - `domains/models/` — AI model configuration per workspace
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

- the intelligence service also writes shared business data through its own tool handlers and repositories; the service boundary is at the HTTP/router layer, not at the database level

Start here when changing:

- LLM provider support
- retrieval pipeline behavior
- prompt orchestration
- tool addition or parameter changes
- AI response shapes

### `services/integrations/`

External integration service.

Important folders:

- `main.py`
  App bootstrap.
- `domains/`
  - `domains/github/` — GitHub accounts, repos, commits, webhooks
  - `domains/webhook/` — webhook processing and validation
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

### `services/automation/`

MCP tool automation service.

Important folders:

- `main.py`
  App bootstrap.
- `domains/`
  - `domains/registry/` — tool discovery and listing
  - `domains/execution/` — tool execution implementations

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
- `infrastructure/load_balancer.py`
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

- GitHub -> integrations service webhook -> commit storage -> intelligence internal analysis -> persisted analyses

### AI Chat And RAG

- frontend -> gateway -> intelligence service -> shared database and embeddings -> model provider

### MCP Tool Execution

- frontend or model integration -> gateway -> automation service -> workspace tool implementation -> shared database

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

## Function Ownership Matrix

| Service | Route families (entry points) | Function ownership | Main dependencies | Diagram references |
|---|---|---|---|---|
| Workspace | `/api/auth/*`, `/api/v1/workspaces/*`, `/api/v1/workspaces/*/projects*`, `/api/v1/workspaces/*/tasks*`, `/api/v1/workspaces/*/oppm*`, `/api/v1/workspaces/*/epics*`, `/api/v1/workspaces/*/user-stories*`, `/api/v1/workspaces/*/sprints*`, `/api/v1/workspaces/*/phases*`, `/api/v1/workspaces/*/dashboard/*`, `/api/v1/notifications*` | Auth/session, tenancy, projects, tasks, OPPM, agile, waterfall, notifications, dashboard | `shared/auth.py`, workspace domains, shared ORM, PostgreSQL, Redis | [S2](flowcharts.md#s2-backend-function-lifecycle-router-to-data), [14](flowcharts.md#14-core-service-function-flow-workspace-to-oppm) |
| Intelligence | `/api/v1/workspaces/*/ai/*`, `/api/v1/workspaces/*/rag/*`, `/api/v1/workspaces/*/projects/*/ai/*`, `/internal/analyze-commits` | Model config, workspace/project chat, RAG retrieval, reindex, AI plan suggestion, OPPM fill/extract, feedback, internal commit analysis | Intelligence domains, tool registry, RAG pipeline, shared ORM/DB, Redis semantic cache, LLM providers | [S2](flowcharts.md#s2-backend-function-lifecycle-router-to-data), [15](flowcharts.md#15-ai-service-function-flow-chat-and-tools) |
| Integrations | `/api/v1/workspaces/*/github-accounts*`, `/api/v1/workspaces/*/git/*`, `/api/v1/workspaces/*/commits*`, `/api/v1/git/webhook` | GitHub accounts, repo config, webhook validation, commit storage, reports, AI handoff trigger | Integration domains, shared ORM/DB, GitHub, intelligence internal endpoint | [S3](flowcharts.md#s3-cross-service-calls-current-runtime), [16](flowcharts.md#16-git-service-function-flow-webhook-to-analysis) |
| Automation | `/api/v1/workspaces/*/mcp/tools`, `/api/v1/workspaces/*/mcp/call` | Tool discovery and execution for workspace-scoped integrations | Automation domains, shared auth context, shared ORM/DB | [S3](flowcharts.md#s3-cross-service-calls-current-runtime), [17](flowcharts.md#17-mcp-service-function-flow-tool-discovery-and-call) |
| Gateway (Python + nginx) | All `/api/*`, `/internal/analyze-commits`, `/mcp`, `/health/*` | Route dispatch, upstream forwarding, timeout policy, health-aware balancing (Python gateway) | `services/gateway/main.py`, `gateway/nginx.conf`, upstream services | [S1](flowcharts.md#s1-end-to-end-service-collaboration-map) |

## Feature Lookup Table

| Feature | First place to look | Canonical feature doc |
|---|---|---|
| Login, signup, refresh | `services/workspace/domains/auth/router.py`, `services/workspace/domains/auth/service.py` | [`features/auth/authentication.md`](../features/auth/authentication.md) |
| Workspace membership and invites | `services/workspace/domains/workspace/router.py`, `services/workspace/domains/workspace/service.py` | [`features/workspace/workspaces.md`](../features/workspace/workspaces.md) |
| Project CRUD | `services/workspace/domains/project/router.py`, `services/workspace/domains/project/service.py` | [`features/project/projects.md`](../features/project/projects.md) |
| Task CRUD and reports | `services/workspace/domains/task/router.py`, `services/workspace/domains/task/service.py` | [`features/project/tasks.md`](../features/project/tasks.md) |
| OPPM board | `services/workspace/domains/oppm/router.py`, `services/workspace/domains/oppm/service.py` | [`features/oppm/spreadsheet-rendering.md`](../features/oppm/spreadsheet-rendering.md) |
| Agile workflows | `services/workspace/domains/agile/router.py`, `services/workspace/domains/agile/service.py` | [`features/project/tasks.md`](../features/project/tasks.md) |
| Waterfall workflows | `services/workspace/domains/waterfall/router.py`, `services/workspace/domains/waterfall/service.py` | [`features/project/projects.md`](../features/project/projects.md) |
| Notifications | `services/workspace/domains/notification/router.py`, `services/workspace/domains/notification/service.py` | [`features/dashboard/dashboard-notifications.md`](../features/dashboard/dashboard-notifications.md) |
| Dashboard | `services/workspace/domains/dashboard/router.py`, `services/workspace/domains/dashboard/service.py` | [`features/dashboard/dashboard-notifications.md`](../features/dashboard/dashboard-notifications.md) |
| AI model settings | `services/intelligence/domains/models/router.py` | [`features/ai/ai-assistant.md`](../features/ai/ai-assistant.md) |
| Chat and weekly summary | `services/intelligence/domains/chat/router.py`, `services/intelligence/domains/chat/service.py` | [`features/ai/ai-assistant.md`](../features/ai/ai-assistant.md) |
| RAG query | `services/intelligence/domains/rag/router.py`, `services/intelligence/domains/rag/service.py` | [`features/ai/ai-assistant.md`](../features/ai/ai-assistant.md) |
| GitHub webhook | `services/integrations/domains/github/router.py`, `services/integrations/domains/github/service.py` | [`features/github/github-integration.md`](../features/github/github-integration.md) |
| MCP tools | `services/automation/domains/registry/router.py`, `services/automation/domains/execution/` | [`features/mcp/mcp-tools.md`](../features/mcp/mcp-tools.md) |

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
3. add migration in `services/workspace/alembic/`
4. add schema in the owning service
5. add repository logic if persistence changes
6. add service logic
7. add route wiring
8. update [api/reference.md](api/reference.md), [database/er-diagram.md](database/er-diagram.md), and [development/testing.md](development/testing.md)
