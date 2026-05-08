# Microservice Architecture Review

> **Date:** May 7, 2026
> **Scope:** Evaluate current service split for simplicity and necessity
> **Goal:** Minimize services without losing separation of concerns

---

## Current State (After ADRs)

The project already went through a consolidation (ADR 001-004). Current runtime:

| Service | Port | Responsibility | Lines of Code* | Status |
|---------|------|----------------|------------------|--------|
| **gateway** | 8080 / 80 | Request routing | ~200 | ✅ Necessary |
| **workspace** | 8000 | Auth, workspace, project, task, OPPM, notifications, dashboard, agile, waterfall | ~15,000 | ✅ Core monolith |
| **intelligence** | 8001 | LLM adapters, RAG, chat, agent loop, skills | ~8,000 | ✅ Justified |
| **integrations** | 8002 | GitHub webhooks, commit storage, commit analysis | ~2,000 | ⚠️ Thin |
| **automation** | 8003 | MCP tool registry (5 tools) | ~500 | ⚠️ Very thin |

*Approximate Python LOC

**Total: 5 services** (1 gateway + 4 business)

---

## Assessment by Service

### 1. Gateway — ✅ KEEP

**Why it's necessary:**
- Single entry point for all API requests
- Handles CORS, request ID forwarding, health checks
- Routes to correct backend service

**Issue:**
- **Two gateways exist:** `services/gateway/` (Python) and `gateway/` (nginx)
- Both have identical routing logic — maintenance burden
- Python gateway is for native dev, nginx for Docker

**Recommendation:**
```
Decision: Keep nginx only, remove Python gateway
Rationale: nginx is simpler, faster, battle-tested
Action: Delete services/gateway/, update docs
Effort: Low
```

---

### 2. Workspace — ✅ KEEP (The Monolith)

**Why it's necessary:**
- Contains 10 DDD domains with tight data coupling
- All tables share `workspace_id` — single JOINs are fast
- ACID transactions across domains

**Domains inside:**
```
domains/
├── auth/           # Login, signup, JWT
├── workspace/      # CRUD, members, invites
├── project/        # CRUD, members
├── task/           # CRUD, reports, dependencies
├── oppm/           # Objectives, timeline, costs, Google Sheets
├── notification/   # Notifications, audit log
├── dashboard/      # Aggregated stats
├── agile/          # Epics, stories, sprints
├── waterfall/      # Phases, documents
└── member/         # Skills, profiles
```

**This is the right approach.** Don't split further.

---

### 3. Intelligence — ✅ KEEP

**Why it's necessary:**
- Different scaling profile (CPU/GPU intensive)
- Different failure mode (LLM outages shouldn't break core app)
- Different team ownership (AI/ML vs backend)

**What's inside:**
```
infrastructure/
├── llm/            # 5 provider adapters (Ollama, Claude, OpenAI, Kimi, DeepSeek)
├── rag/            # Retrievers, guardrails, memory, cache
├── skills/         # Skill system + OPPM skill
├── tools/          # Tool registry (24 tools)
├── planner/        # Agent loop, plan generation
└── learning/       # Feedback memory
```

**This is well-justified.** Keep separate.

---

### 4. Integrations — ⚠️ QUESTIONABLE

**What it does:**
- GitHub OAuth connection
- Webhook receiver (`/api/v1/git/webhook`)
- Commit storage (`commit_events` table)
- Calls AI for commit analysis (`/internal/analyze-commits`)

**Why it was split:**
- Webhooks need public internet exposure
- Isolates GitHub-specific code

**Why it could be merged into Workspace:**
- Only ~2,000 LOC
- Tightly coupled to `projects` and `commit_events` tables
- Webhook endpoint could live in `domains/github/` within workspace
- No independent scaling need

**Recommendation:**
```
Decision: MERGE into workspace service
Rationale: Too small to justify separate service, tight coupling
Action: Move domains/github/ into services/workspace/domains/
         Keep webhook route public-facing
Effort: Medium (update gateway routing, docker-compose)
Risk: Low
```

---

### 5. Automation — ⚠️ MERGE INTO INTELLIGENCE

**What it does:**
- MCP tool registry (5 read-only tools)
- HTTP endpoint: `GET /mcp/tools`, `POST /mcp/call`

**Tools:**
| Tool | Description | Data Source |
|------|-------------|-------------|
| `list_projects` | List workspace projects | PostgreSQL |
| `get_project_status` | Get project status | PostgreSQL |
| `get_task_summary` | Tasks by status | PostgreSQL |
| `list_at_risk_objectives` | At-risk objectives | PostgreSQL |
| `summarize_recent_commits` | Commit summary | PostgreSQL |

**Why it should be merged:**
- Only ~500 LOC
- Only used by Intelligence service
- No independent scaling need
- Adds deployment complexity for no benefit

**Recommendation:**
```
Decision: MERGE into intelligence service
Rationale: MCP tools are AI infrastructure, not standalone service
Action: Move services/automation/domains/execution/ into services/intelligence/infrastructure/mcp_tools/
         Keep registry router in intelligence/routers/
Effort: Low
Risk: None
```

---

## Proposed Target Architecture

```
Before: 5 services          After: 3 services
┌─────────────┐            ┌─────────────┐
│   Gateway   │            │   Gateway   │  (nginx only)
│  (Python)   │            │   (nginx)   │
└─────────────┘            └─────────────┘
┌─────────────┐            ┌─────────────┐
│   Gateway   │            │  Workspace  │  (monolith + github)
│   (nginx)   │            │   :8000     │
└─────────────┘            └─────────────┘
┌─────────────┐            ┌─────────────┐
│  Workspace  │            │ Intelligence│  (AI + MCP tools)
│   :8000     │            │   :8001     │
└─────────────┘            └─────────────┘
┌─────────────┐
│ Intelligence│
│   :8001     │
└─────────────┘
┌─────────────┐
│Integrations │
│   :8002     │
└─────────────┘
┌─────────────┐
│ Automation  │
│   :8003     │
└─────────────┘
```

**Result: 5 services → 3 services**

---

## Migration Plan

### Phase 1: Remove Python Gateway (1 day)
- [ ] Delete `services/gateway/`
- [ ] Update `docker-compose.yml` to remove gateway service
- [ ] Update `docker-compose.microservices.yml` to remove gateway service
- [ ] Update docs to mention nginx-only
- [ ] Test nginx routing still works

### Phase 2: Merge Automation into Intelligence (2 days)
- [ ] Move `services/automation/domains/execution/` → `services/intelligence/infrastructure/mcp_tools/`
- [ ] Move `services/automation/domains/registry/router.py` → `services/intelligence/routers/mcp.py`
- [ ] Update imports in moved files
- [ ] Update `services/intelligence/main.py` to include MCP router
- [ ] Update gateway nginx.conf: `/mcp` → `intelligence:8001`
- [ ] Remove `services/automation/` directory
- [ ] Update `docker-compose.yml` to remove automation service
- [ ] Test MCP tool calls still work

### Phase 3: Merge Integrations into Workspace (3 days)
- [ ] Move `services/integrations/domains/github/` → `services/workspace/domains/github/`
- [ ] Move `services/integrations/routers/health.py` → merge into workspace health
- [ ] Update imports in moved files
- [ ] Update `services/workspace/main.py` to include GitHub router
- [ ] Update gateway nginx.conf:
  - `/api/v1/workspaces/*/github-accounts` → `workspace:8000`
  - `/api/v1/workspaces/*/commits` → `workspace:8000`
  - `/api/v1/workspaces/*/git/*` → `workspace:8000`
  - `/api/v1/git/webhook` → `workspace:8000`
- [ ] Remove `services/integrations/` directory
- [ ] Update `docker-compose.yml` to remove integrations service
- [ ] Test GitHub webhook still works

### Phase 4: Documentation Update (1 day)
- [ ] Update `docs/architecture/service-boundaries.md`
- [ ] Update `docs/MICROSERVICES-REFERENCE.md`
- [ ] Update `docs/AI-AGENT-ARCHITECTURE-RESEARCH.md`
- [ ] Update `docs/AI-AGENT-IMPLEMENTATION-PLAN.md`
- [ ] Update `CLAUDE.md`
- [ ] Update `README.md`

**Total effort: ~1 week**
**Risk: Low** (all services are stateless, database is shared)

---

## Why This Is Better

| Before | After | Benefit |
|--------|-------|---------|
| 5 services to deploy | 3 services | Less ops overhead |
| 5 health checks | 3 health checks | Faster monitoring |
| 5 Dockerfiles | 3 Dockerfiles | Less build time |
| 5 service logs | 3 service logs | Easier debugging |
| 2 gateways | 1 gateway | No routing confusion |
| Gateway routes to 4 services | Gateway routes to 2 services | Simpler nginx.conf |

---

## What NOT to Do

❌ **Don't split workspace further** — The modular monolith is correct. Domains are well-organized.

❌ **Don't merge intelligence into workspace** — AI has different scaling, failure modes, and team ownership.

❌ **Don't create more services** — No new service unless it has:
- Independent scaling needs
- Different failure domain
- Different team ownership
- >5,000 LOC

---

## Summary

| Service | Current | Recommended | Action |
|---------|---------|-------------|--------|
| Gateway (Python) | Active | **Remove** | Delete, use nginx only |
| Gateway (nginx) | Active | **Keep** | ✅ |
| Workspace | Active | **Keep** | ✅ |
| Intelligence | Active | **Keep** | ✅ |
| Integrations | Active | **Merge into Workspace** | Move code, update routing |
| Automation | Active | **Merge into Intelligence** | Move code, update routing |

**Final count: 5 services → 3 services**

This is a **minimal viable microservice architecture** for this project:
- **Workspace**: Core business logic (monolith)
- **Intelligence**: AI/ML (separate for scaling)
- **Gateway**: nginx (single entry point)

---

*Reviewed: May 7, 2026*
*Recommended by: OPPM Architect*
