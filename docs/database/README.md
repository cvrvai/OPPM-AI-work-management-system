# Database Documentation Hub

Last updated: 2026-04-20

## Purpose

This hub organizes database documentation by service so future updates are easier to plan and execute.

It complements the canonical root docs:

- [DATABASE-SCHEMA.md](../DATABASE-SCHEMA.md)
- [ERD.md](../ERD.md)

## Database Docs By Service

| Service | Database doc | Primary database role |
|---|---|---|
| Core | [core/README.md](core/README.md) | Main schema owner, migrations, and most business data writes |
| AI | [ai/README.md](ai/README.md) | AI model config, embeddings, audit feedback, and AI-driven shared-data writes |
| Git | [git/README.md](git/README.md) | GitHub integration tables, commit ingestion, analysis persistence |
| MCP | [mcp/README.md](mcp/README.md) | Tool-mediated reads/writes via workspace-scoped tool functions |
| Gateway | [gateway/README.md](gateway/README.md) | No direct DB ownership; routing-only layer |

## ER Diagram View

- [ER-DIAGRAM.md](ER-DIAGRAM.md) (service-oriented ER view)
- [../ERD.md](../ERD.md) (canonical full ERD)

## Update Checklist

1. If table/column constraints change, update `../DATABASE-SCHEMA.md`.
2. If relationships change, update both `ER-DIAGRAM.md` and `../ERD.md`.
3. If service data ownership changes, update relevant `database/<service>/README.md`.

