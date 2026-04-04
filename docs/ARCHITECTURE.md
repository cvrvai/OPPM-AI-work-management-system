# Architecture

Last updated: 2026-04-04

## Purpose

This document describes the current runtime architecture of the OPPM AI Work Management System as it exists in code today. It replaces older notes that mixed the previous monolith assumptions with the current microservices implementation.

Use this file for system-level orientation. Use the supporting docs for detail:

- [API-REFERENCE.md](API-REFERENCE.md)
- [ERD.md](ERD.md)
- [FLOWCHARTS.md](FLOWCHARTS.md)
- [FRONTEND-REFERENCE.md](FRONTEND-REFERENCE.md)
- [MICROSERVICES-REFERENCE.md](MICROSERVICES-REFERENCE.md)
- [MICROSERVICES-REVIEW.md](MICROSERVICES-REVIEW.md)
- [PHASE-TRACKER.md](PHASE-TRACKER.md)
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

- workspace and project chat
- weekly summaries
- AI model configuration per workspace
- project plan suggestion and commit of suggested plans
- workspace reindexing for retrieval
- RAG query endpoint
- internal commit analysis endpoint called by the git service

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

## Data Architecture

### Primary Database

The backend uses PostgreSQL accessed through SQLAlchemy async sessions.

Important facts:

- the ORM models live in `shared/models/`
- migrations live in `services/core/alembic/`
- `supabase/schema.sql` is a reference schema snapshot, not the authoritative migration runner
- RAG embeddings are stored in the same database
- audit and notification data are part of the same application database

### Redis

Redis is used as a support dependency, not as the source of truth.

Current roles:

- token blacklist support on signout
- rate limiting support
- cache support for selected flows
- workspace membership cache bootstrap support

If Redis is unavailable, the app can still start, but some performance and security-related behaviors degrade.

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

See [FRONTEND-REFERENCE.md](FRONTEND-REFERENCE.md) for the detailed folder-level map.

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
3. [FRONTEND-REFERENCE.md](FRONTEND-REFERENCE.md)
4. [API-REFERENCE.md](API-REFERENCE.md)
5. [ERD.md](ERD.md)
