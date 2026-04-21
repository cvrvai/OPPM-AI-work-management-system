# OPPM AI Work Management System

AI-powered **One Page Project Manager (OPPM)** — a multi-tenant, workspace-scoped project management platform. Applicable to any industry: construction, finance, healthcare, manufacturing, education, and more.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS v4 + TanStack Query v5 + Zustand v5 |
| Backend | Python FastAPI (microservices: core, ai, git, mcp) |
| Database | PostgreSQL via Supabase (connection string only — self-hosted DB) |
| Auth | Local HS256 JWT validation in `shared/auth.py` with refresh-token persistence |
| AI | Multi-model: Ollama, Kimi K2.5, Claude (Anthropic), OpenAI — plug-in adapters |
| API Gateway | FastAPI gateway service (port 8080) or Nginx in production |
| Deployment | Docker Compose (monolith or microservices) |

## Quick Start (Development)

### Prerequisites
- Python 3.11+, Node.js 20+, Docker (optional)
- A running PostgreSQL instance (Supabase cloud or local Docker)

### 1. Clone & configure

```powershell
git clone <repo>
cd "OPPM AI work management system"
copy .env.example .env
# Edit .env — set DATABASE_URL, JWT_SECRET, and optional AI API keys
```

### 2. Start backend services

```powershell
# Each service in its own terminal:
.\start_core.ps1    # Core API  → http://localhost:8000
.\start_ai.ps1      # AI service → http://localhost:8001
.\start_git.ps1     # Git service → http://localhost:8002
.\start_mcp.ps1     # MCP service → http://localhost:8003
.\start_gateway.ps1 # Gateway   → http://localhost:8080
```

Or use Docker Compose:
```powershell
docker compose -f docker-compose.microservices.yml up --build
```

### 3. Start frontend

```powershell
cd frontend
npm install
npm run dev       # http://localhost:5173
```

The Vite dev proxy forwards `/api` → `http://localhost:8080`.

### 4. Verify

```powershell
Invoke-RestMethod http://localhost:8080/health   # { status: "ok", service: "gateway" }
.\test_api.ps1                                   # 48 PASS / 0 FAIL / 4 SKIP
```

### 5. Seed demo industry data (optional)

```powershell
.\seed_demo.ps1
```

Creates 5 demo accounts across Architecture, Finance, Healthcare, Manufacturing, and Education — each with 2 fully-populated OPPM projects.

| Email | Password | Industry |
|---|---|---|
| arch@demo.oppm | Demo@12345 | Architecture & Construction |
| finance@demo.oppm | Demo@12345 | Finance & Banking |
| health@demo.oppm | Demo@12345 | Healthcare |
| mfg@demo.oppm | Demo@12345 | Manufacturing |
| edu@demo.oppm | Demo@12345 | Higher Education |

## Architecture

```
Browser → Frontend (React/Vite :5173)
             ↓ /api (Vite proxy in dev)
          Gateway (:8080)
           ├── /api/auth/*                         → Core service (:8000)
           ├── /api/v1/workspaces/*/ai/*          → AI service   (:8001)
           ├── /api/v1/workspaces/*/rag/*         → AI service   (:8001)
           ├── /api/v1/workspaces/*/github-*      → Git service  (:8002)
           ├── /api/v1/workspaces/*/git/*         → Git service  (:8002)
           ├── /api/v1/workspaces/*/commits*      → Git service  (:8002)
           └── /api/v1/workspaces/*/mcp/*         → MCP service  (:8003)
                    ↓
              PostgreSQL (Supabase)
```

**GitHub Commit Pipeline:**
1. Developer pushes code to GitHub
2. GitHub fires webhook to Git service (`POST /api/v1/git/webhook`)
3. HMAC-SHA256 signature validated
4. Commit diff + metadata extracted and stored
5. AI service analyses commit against OPPM objectives (if model is configured)
6. Analysis stored — alignment score, task suggestions, commit classification
7. OPPM dashboard auto-updates with commit insights

## Project Structure

```
├── frontend/                    React + Vite + TypeScript
│   └── src/
│       ├── pages/               Dashboard, Projects, OPPMView, Commits, Settings, etc.
│       ├── components/          ChatFAB, ChatPanel, workspace selector, layout
│       ├── lib/                 api.ts (fetch wrapper), tokens.ts, utils.ts
│       ├── stores/              authStore, workspaceStore, chatStore (Zustand)
│       └── types/               TypeScript interfaces for all API types
├── services/
│   ├── core/                    Auth, workspaces, projects, tasks, OPPM, notifications
│   ├── ai/                      Chat, weekly summary, RAG, embedding, LLM adapters
│   ├── git/                     GitHub accounts, repos, webhooks, commit analysis
│   ├── mcp/                     Model Context Protocol endpoints
│   └── gateway/                 FastAPI reverse-proxy gateway
├── shared/                      Shared Python package (auth, database client, schemas)
├── supabase/
│   └── schema.sql               Full DDL — reference schema (not auto-applied)
├── docs/                        Architecture, ERD, API Reference, Flowcharts, etc.
├── seed_demo.ps1                 Industry demo data seed script
├── test_api.ps1                  Full API test suite (48 tests)
├── docker-compose.yml            Monolith compose
└── docker-compose.microservices.yml  Microservices compose
```

## Key Features

- **Multi-tenant workspaces** — invite members, role-based access (owner / admin / member)
- **OPPM board** — objectives with weekly status dots, inline editing, RAG risk tracking, cost bar charts
- **AI chat** — context-aware assistant using RAG over your project data; pluggable LLM (Ollama, OpenAI, Anthropic, Kimi)
- **GitHub integration** — link repos to projects; auto-analyse commits against OPPM objectives
- **Weekly AI summary** — structured status report generated from live project data
- **Notifications** — real-time unread count, per-event types
- **Seed data** — 5 non-software industries with realistic project data for demos

## Documentation

| File | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, service map, data flow |
| [docs/AI-SYSTEM-CONTEXT.md](docs/AI-SYSTEM-CONTEXT.md) | Fast start reference for future AI or human updates: feature flows, edit hotspots, schema design, and verified drift notes |
| [docs/API-REFERENCE.md](docs/API-REFERENCE.md) | Current public route reference and contract notes |
| [docs/frontend/FRONTEND-REFERENCE.md](docs/frontend/FRONTEND-REFERENCE.md) | Frontend folder map, route ownership, state flow, and feature entry points |
| [docs/MICROSERVICES-REFERENCE.md](docs/MICROSERVICES-REFERENCE.md) | Service ownership, shared package map, gateway routing, and backend feature entry points |
| [docs/services/README.md](docs/services/README.md) | Service-level feature inventory hub for core/ai/git/mcp/gateway and upgrade planning |
| [docs/database/README.md](docs/database/README.md) | Database documentation hub by service plus ER diagram view |
| [docs/ERD.md](docs/ERD.md) | Current relational model and relationship notes |
| [docs/FLOWCHARTS.md](docs/FLOWCHARTS.md) | Runtime flows for auth, invites, projects, AI, GitHub, and routing |
| [docs/TESTING-GUIDE.md](docs/TESTING-GUIDE.md) | Automated checks, smoke scripts, and manual test matrix |
| [docs/PHASE-TRACKER.md](docs/PHASE-TRACKER.md) | Active per-task tracker for ongoing implementation work; older trackers are archived in `docs/phase-history/` |
| [docs/review/MICROSERVICES-REVIEW.md](docs/review/MICROSERVICES-REVIEW.md) | Architecture assessment, risks, and cleanup priorities |
| [docs/SRS.md](docs/SRS.md) | Product-level software requirements specification |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local development setup and conventions |

