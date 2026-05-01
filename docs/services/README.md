# Service Documentation Hub

Last updated: 2026-04-20

## Purpose

This hub is the feature-level maintenance map for backend services.  
Use it before changing any service behavior, adding features, or planning architecture upgrades (for example Graph API or GraphRAG).

## Service Index

| Service | Doc | Owns | Canonical feature docs |
|---|---|---|---|
| Workspace | [workspace/README.md](workspace/README.md) | Auth, workspaces, projects, tasks, OPPM, agile/waterfall, notifications, dashboard | [features/auth/authentication.md](../features/auth/authentication.md), [features/workspace/workspaces.md](../features/workspace/workspaces.md), [features/workspace/team-invites.md](../features/workspace/team-invites.md), [features/project/projects.md](../features/project/projects.md), [features/project/tasks.md](../features/project/tasks.md), [features/oppm/structured-planning.md](../features/oppm/structured-planning.md), [features/oppm/spreadsheet-rendering.md](../features/oppm/spreadsheet-rendering.md), [features/dashboard/dashboard-notifications.md](../features/dashboard/dashboard-notifications.md) |
| Intelligence | [intelligence/README.md](intelligence/README.md) | AI models, chat, RAG, reindex, plan suggestion, feedback, internal commit analysis | [features/ai/ai-assistant.md](../features/ai/ai-assistant.md), [features/oppm/ai-fill-and-extract.md](../features/oppm/ai-fill-and-extract.md), [features/github/github-integration.md](../features/github/github-integration.md) |
| Integrations | [integrations/README.md](integrations/README.md) | GitHub accounts, repo configs, webhook ingestion, commits, reports | [features/github/github-integration.md](../features/github/github-integration.md) |
| Automation | [automation/README.md](automation/README.md) | Workspace tool listing and execution | [features/mcp/mcp-tools.md](../features/mcp/mcp-tools.md) |
| Gateway | [gateway/README.md](gateway/README.md) | Request routing, forwarding, timeout and health routing policy | — |

Each service page includes a dedicated Mermaid flowchart for that service.

## How To Use This Hub

1. Open the target service doc.
2. Confirm route ownership and data touchpoints.
3. For full feature flows (frontend files, tables, caveats), open the linked canonical doc in `docs/features/`.
4. Follow the change-impact checklist in that service doc.
5. Update `docs/API-REFERENCE.md`, `docs/FLOWCHARTS.md`, and related docs if contracts or behavior changed.

## Cross-Service Update Checklist

- Route ownership changed -> update both Python gateway and nginx gateway rules.
- API contract changed -> update `docs/API-REFERENCE.md`.
- Data model changed -> update `docs/database/schema.md` and `docs/database/ER-DIAGRAM.md`.
- Runtime flow changed -> update `docs/FLOWCHARTS.md`.
- Service responsibilities changed -> update `docs/MICROSERVICES-REFERENCE.md` and this hub.

