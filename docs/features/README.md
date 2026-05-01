# Feature Documentation

Last updated: 2026-05-01

This folder contains canonical documentation for every major feature in the OPPM AI Work Management System.

Each file follows a consistent template:
- **What it does** — 2-3 sentence summary
- **How it works** — Step-by-step flow
- **Frontend files** — Links to source
- **Backend files** — Links to source
- **Primary tables** — Database tables involved
- **Update notes** — Caveats, drift, and things to watch

## Feature Index

| # | Feature | File | Service |
|---|---------|------|---------|
| 1 | Authentication & Session Bootstrap | [`auth/authentication.md`](auth/authentication.md) | Workspace |
| 2 | Workspace Bootstrap, Tenancy & Authorization | [`workspace/workspaces.md`](workspace/workspaces.md) | Workspace |
| 3 | Team, Invites & Member Skills | [`workspace/team-invites.md`](workspace/team-invites.md) | Workspace |
| 4 | Projects & Project Membership | [`project/projects.md`](project/projects.md) | Workspace |
| 5 | Tasks, Hierarchy, Dependencies & Daily Reports | [`project/tasks.md`](project/tasks.md) | Workspace |
| 6 | Structured OPPM Planning Data | [`oppm/structured-planning.md`](oppm/structured-planning.md) | Workspace |
| 7 | OPPM Spreadsheet, Template, Import/Export & AI Fill | [`oppm/spreadsheet-rendering.md`](oppm/spreadsheet-rendering.md) | Workspace + Intelligence |
| 8 | AI Assistant, Chat, RAG, Plan Suggestion & Model Config | [`ai/ai-assistant.md`](ai/ai-assistant.md) | Intelligence |
| 9 | GitHub Integration, Commits & Commit Analysis | [`github/github-integration.md`](github/github-integration.md) | Integrations + Intelligence |
| 10 | Dashboard & Notifications | [`dashboard/dashboard-notifications.md`](dashboard/dashboard-notifications.md) | Workspace |
| 11 | MCP Tools | [`mcp/mcp-tools.md`](mcp/mcp-tools.md) | Automation |
| 12 | Tool Registry & Agentic Loop | [`ai/tool-registry.md`](ai/tool-registry.md) | Intelligence |

## Sub-Folders

| Folder | Features |
|--------|----------|
| [`auth/`](auth/) | Authentication, session bootstrap, JWT |
| [`workspace/`](workspace/) | Workspace tenancy, membership, invites, skills |
| [`project/`](project/) | Projects, tasks, hierarchy, dependencies, reports |
| [`oppm/`](oppm/) | OPPM structured planning, spreadsheet, Google Sheets, AI fill |
| [`ai/`](ai/) | AI assistant, chat, RAG, tool registry, agentic loop |
| [`github/`](github/) | GitHub integration, commits, commit analysis |
| [`dashboard/`](dashboard/) | Dashboard stats and notifications |
| [`mcp/`](mcp/) | MCP tool discovery and execution |

## How This Relates To Other Docs

- For **system architecture** (runtime topology, service boundaries, C4 diagrams), see [`../architecture/`](../architecture/)
- For **API endpoint reference**, see [`../api/reference.md`](../api/reference.md)
- For **database schema**, see [`../database/schema.md`](../database/schema.md)
- For **service deep dives**, see [`../services/`](../services/)
- For **frontend patterns**, see [`../frontend/FRONTEND-REFERENCE.md`](../frontend/FRONTEND-REFERENCE.md)
- For **AI pipeline details**, see [`../ai/AI-PIPELINE-REFERENCE.md`](../ai/AI-PIPELINE-REFERENCE.md)
- For **tool registry details**, see [`../ai/TOOL-REGISTRY-REFERENCE.md`](../ai/TOOL-REGISTRY-REFERENCE.md)
