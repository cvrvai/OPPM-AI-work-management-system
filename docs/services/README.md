# Service Documentation Hub

Last updated: 2026-04-20

## Purpose

This hub is the feature-level maintenance map for backend services.  
Use it before changing any service behavior, adding features, or planning architecture upgrades (for example Graph API or GraphRAG).

## Service Index

| Service | Doc | Owns |
|---|---|---|
| Core | [core/README.md](core/README.md) | Auth, workspaces, projects, tasks, OPPM, agile/waterfall, notifications, dashboard |
| AI | [ai/README.md](ai/README.md) | AI models, chat, RAG, reindex, plan suggestion, feedback, internal commit analysis |
| Git | [git/README.md](git/README.md) | GitHub accounts, repo configs, webhook ingestion, commits, reports |
| MCP | [mcp/README.md](mcp/README.md) | Workspace tool listing and execution |
| Gateway | [gateway/README.md](gateway/README.md) | Request routing, forwarding, timeout and health routing policy |

Each service page includes a dedicated Mermaid flowchart for that service.

## How To Use This Hub

1. Open the target service doc.
2. Confirm route ownership and data touchpoints.
3. Follow the change-impact checklist in that service doc.
4. Update `docs/API-REFERENCE.md`, `docs/FLOWCHARTS.md`, and related docs if contracts or behavior changed.

## Cross-Service Update Checklist

- Route ownership changed -> update both Python gateway and nginx gateway rules.
- API contract changed -> update `docs/API-REFERENCE.md`.
- Data model changed -> update `docs/DATABASE-SCHEMA.md` and `docs/ERD.md`.
- Runtime flow changed -> update `docs/FLOWCHARTS.md`.
- Service responsibilities changed -> update `docs/MICROSERVICES-REFERENCE.md` and this hub.

