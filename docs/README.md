# Documentation

Welcome to the project documentation. This is the entry point for understanding the system, onboarding, and finding answers.

## Quick Links

| I want to... | Go to |
|---|---|
| Understand the system architecture | [`architecture/overview.md`](architecture/overview.md) |
| Know which service owns what | [`architecture/service-boundaries.md`](architecture/service-boundaries.md) |
| See API endpoints and contracts | [`api/reference.md`](api/reference.md) |
| Understand the database schema | [`database/schema.md`](database/schema.md) |
| Understand a specific feature | [`features/README.md`](features/README.md) |
| Set up my local environment | [`development/setup.md`](development/setup.md) |
| Understand why we made a decision | [`decisions/`](decisions/) |
| See C4 architecture diagrams | [`architecture/c4/`](architecture/c4/) |
| Read past architecture reviews | [`architecture/reviews/`](architecture/reviews/) |

---

## Documentation Structure

### [`decisions/`](decisions/) — Architecture Decision Records (ADRs)

Immutable records of significant architectural decisions. Read these to understand **why** the system is built this way.

| ADR | Decision |
|---|---|
| [001](decisions/001-use-modular-monolith.md) | Use modular monolith with DDD domains |
| [002](decisions/002-rename-services-to-domain-language.md) | Rename services to domain language |
| [003](decisions/003-adopt-ddd-folder-structure.md) | Adopt DDD folder structure |
| [004](decisions/004-remove-dead-microservices.md) | Remove dead microservices |
| [005](decisions/005-consolidate-documentation-structure.md) | Consolidate documentation structure |

### [`architecture/`](architecture/) — System Architecture

High-level system design, service boundaries, and runtime topology.

- [`overview.md`](architecture/overview.md) — System overview, runtime topology, data architecture
- [`service-boundaries.md`](architecture/service-boundaries.md) — What each service owns, routing, ports
- [`ai-system-context.md`](architecture/ai-system-context.md) — High-signal reference for AI-assisted updates
- [`srs.md`](architecture/srs.md) — Software Requirements Specification
- [`flowcharts.md`](architecture/flowcharts.md) — Service interaction and function-level flows
- [`c4/`](architecture/c4/) — C4 model diagrams (Context, Container, Component)
- [`reviews/`](architecture/reviews/) — Past architecture reviews and assessments

### [`api/`](api/) — API Documentation

- [`reference.md`](api/reference.md) — Endpoint reference, request/response contracts

### [`features/`](features/) — Feature Documentation

Canonical documentation for every major feature. Each file explains what the feature does, how it works, which files to open, and which tables it touches.

- [`README.md`](features/README.md) — Feature index and cross-reference matrix
- [`authentication.md`](features/authentication.md) — Login, signup, JWT, session bootstrap
- [`workspaces.md`](features/workspaces.md) — Tenancy, workspace CRUD, authorization
- [`team-invites.md`](features/team-invites.md) — Members, invites, skills
- [`projects.md`](features/projects.md) — Project CRUD and membership
- [`tasks.md`](features/tasks.md) — Tasks, hierarchy, dependencies, reports
- [`ai-assistant.md`](features/ai-assistant.md) — Chat, RAG, plan suggestion, model config
- [`github-integration.md`](features/github-integration.md) — GitHub, webhooks, commit analysis
- [`dashboard-notifications.md`](features/dashboard-notifications.md) — Dashboard and notifications
- [`mcp-tools.md`](features/mcp-tools.md) — MCP tool registry and execution
- [`tool-registry.md`](features/tool-registry.md) — Agentic tool loop
- [`oppm/`](features/oppm/) — OPPM sub-features (structured planning, spreadsheet, Google Sheets, AI fill, session recovery)

### [`database/`](database/) — Data Layer

- [`schema.md`](database/schema.md) — Table definitions, columns, constraints, indexes
- [`er-diagram.md`](database/er-diagram.md) — Entity-relationship diagrams

### [`services/`](services/) — Service Deep Dives

Per-service documentation that mirrors the `services/` code folder.

- `workspace.md` — Main business monolith (auth, projects, tasks, OPPM)
- `intelligence.md` — LLM, RAG, chat, analysis
- `integrations.md` — GitHub, webhooks, external connectors
- `automation.md` — MCP tool registry and execution

### [`development/`](development/) — Developer Onboarding

- [`setup.md`](development/setup.md) — Local development setup, commands, environment
- [`testing.md`](development/testing.md) — Testing strategy, test structure, manual checklist

### [`runbooks/`](runbooks/) — Operations

Operational procedures for running the system in production.

- `deployment.md` — Deployment procedures
- `incident-response.md` — Incident response playbooks
- `troubleshooting.md` — Common issues and fixes

### [`frontend/`](frontend/) — Frontend Documentation

- [`FRONTEND-REFERENCE.md`](frontend/FRONTEND-REFERENCE.md) — Frontend architecture and patterns

### [`oppm/`](oppm/) — OPPM Domain (Legacy)

> **Note:** OPPM feature documentation has moved to [`features/oppm/`](features/oppm/). These files are kept for reference but may be outdated.

- [`OPPM-ARCHITECTURE.md`](oppm/OPPM-ARCHITECTURE.md) — OPPM-specific architecture
- [`google-sheets-linked-form.md`](oppm/google-sheets-linked-form.md) — Google Sheets integration
- [`google-sheet-edit-session-recovery.md`](oppm/google-sheet-edit-session-recovery.md) — Session recovery

---

## How to Use This Documentation

1. **New to the project?** Start with [`architecture/overview.md`](architecture/overview.md) and [`development/setup.md`](development/setup.md)
2. **Implementing a feature?** Read [`features/README.md`](features/README.md) to find the feature doc, then open the listed source files
3. **Changing the database?** Read [`database/schema.md`](database/schema.md) and check [`decisions/`](decisions/) for data architecture decisions
4. **Wondering why something is this way?** Check [`decisions/`](decisions/) for the ADR
5. **Debugging a production issue?** Check [`runbooks/`](runbooks/) for troubleshooting guides

---

## Documentation Principles

- **Decisions are immutable** — ADRs don't change after acceptance. Supersede with a new ADR if needed.
- **Code is the source of truth** — If docs and code disagree, the code wins. Update the docs.
- **One doc per concern** — Don't mix architecture, API, and operational docs in one file.
- **Link liberally** — Every doc should link to related docs. No doc is an island.

---

Last updated: 2026-05-01
