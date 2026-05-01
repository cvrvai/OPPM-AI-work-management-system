# ADR 002: Rename Services to Domain Language

## Status
Accepted (2026-05-01)

## Context
The original service names were technical/implementation labels:

| Old Name | Problem |
|---|---|
| `core` | Says "I'm important" but not what it does. Lazy default from microservices tutorials. |
| `ai` | Vague. Is it chat? RAG? Model hosting? Analysis? |
| `git` | Misleading — we don't run `git` commands. We integrate with **GitHub** (accounts, webhooks, repos). |
| `mcp` | Acronym-only. New developers have no idea what this does without reading docs. |

The product is evolving from "OPPM AI Work Management System" to a general **enterprise work management platform**. The names should sound like business capabilities, not tech stack labels.

## Decision
Rename services to capability-based names:

| Old | New | Rationale |
|---|---|---|
| `core` | `workspace` | The workspace is the tenant boundary. All data lives inside a workspace. Standard term in enterprise SaaS (Slack, Notion, Asana). |
| `ai` | `intelligence` | Covers chat, retrieval, analysis, plan suggestions, forecasting. Scales if we add predictive analytics. |
| `git` | `integrations` | GitHub is just one external system. Future: GitLab, Bitbucket, Azure DevOps, Jira, Slack. |
| `mcp` | `automation` | MCP tools are about executing actions automatically. "Automation" is what enterprise customers buy. |
| `gateway` | `gateway` | Keep it — universally understood. |

## Consequences

### Positive
- **Capability-based naming** — an architect sees `workspace`, `intelligence`, `integrations`, `automation` and immediately understands the domains
- **No vendor lock-in in names** — `integrations` is honest about the role
- **Scales mentally** — adding `billing`, `analytics`, `search` later fits the same convention

### Negative
- **Cross-cutting rename** — Docker Compose, nginx.conf, Python gateway, service-to-service URLs, all docs must update
- **Folder paths changed** — `services/core/` → `services/workspace/`, `services/git/` → `services/integrations/`
- **Mental model shift** — team must learn new names

## Related Decisions
- [ADR 001: Use Modular Monolith with DDD Domains](001-use-modular-monolith.md)
- [ADR 003: Adopt DDD Folder Structure](003-adopt-ddd-folder-structure.md)
