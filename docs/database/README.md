# Database Documentation Hub

Last updated: 2026-05-01

## Purpose

This is the **single entry point** for all database documentation.

There are only **two database docs** you need to know about:

| Doc | Purpose | When to update |
|---|---|---|
| [schema.md](schema.md) | **Canonical reference** — every table, column, constraint, index (32 tables) | When tables/columns/constraints change |
| [ER-DIAGRAM.md](ER-DIAGRAM.md) | **Visual ER diagram** — Mermaid relationship map | When foreign keys or relationships change |

## Single Source of Truth

The actual schema lives in code:

- **`shared/models/`** — SQLAlchemy ORM classes (source of truth)
- **`services/workspace/alembic/versions/`** — Migration history

## Update Rule

> **Schema changes? Update `shared/models/` first, then `docs/database/schema.md`.**
> **Relationship changes? Update `docs/database/ER-DIAGRAM.md`.**

That's it. No other database docs exist.

## Service Database Ownership (Quick Reference)

| Service | Tables it owns/writes |
|---|---|
| **Workspace** | All business tables: users, workspaces, projects, tasks, OPPM, agile, waterfall, notifications, audit_log |
| **Intelligence** | `ai_models`, `document_embeddings` (plus reads/writes shared tables via tools) |
| **Integrations** | `github_accounts`, `repo_configs`, `commit_events`, `commit_analyses` |
| **Automation** | No dedicated tables (reads/writes shared tables via MCP tools) |
| **Gateway** | No database access |

## Where to find service-specific docs

For feature-level service docs (routes, flowcharts, architecture), see:

- [docs/services/workspace/README.md](../services/workspace/README.md)
- [docs/services/intelligence/README.md](../services/intelligence/README.md)
- [docs/services/integrations/README.md](../services/integrations/README.md)
- [docs/services/automation/README.md](../services/automation/README.md)
- [docs/services/gateway/README.md](../services/gateway/README.md)

