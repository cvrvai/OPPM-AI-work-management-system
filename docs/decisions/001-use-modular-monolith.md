# ADR 001: Use Modular Monolith with DDD Domains

## Status
Accepted (2026-05-01)

## Context
The backend had a hybrid microservices structure with 9 service folders but only 5 were actually wired to the gateway:

- Active: `core`, `ai`, `git`, `mcp`, `gateway`
- Dead/incomplete: `auth`, `workspace`, `project`, `notification`

The `core` service contained all business logic (auth, workspace, project, task, OPPM, notifications) but was named ambiguously. The schema showed tight coupling: `Project` references `Workspace`, `Task` references `Project`, `OPPMObjective` references `Project` — every table traces back to `workspace_id`.

We considered:
1. **Full microservices split** — extract `auth`, `workspace`, `project`, `notification` into separate services
2. **Keep monolith, rename only** — keep everything in `core`, just rename it
3. **Modular monolith with DDD domains** — keep one runtime service, organize internally by business domain

## Decision
Adopt **Option 3: Modular monolith with DDD domains**.

- Keep `workspace` as the single main service (was `core`)
- Organize internally into `domains/{business-domain}/` folders
- Each domain contains its own router, service, repository, and schemas
- Extract only `intelligence`, `integrations`, and `automation` as separate services (different scaling/security profiles)

## Consequences

### Positive
- **No distributed transactions** — workspace, project, task creation stays ACID
- **No cross-service queries** — "show me tasks in my workspace" is a single JOIN
- **Extractable later** — when `project` outgrows the monolith, copy `domains/project/` to `services/project/`
- **Faster development** — one service to deploy, one database to migrate
- **Clear boundaries** — a developer opens `domains/task/` and sees everything

### Negative
- **Service is large** — ~10 domains in one codebase
- **Cross-domain imports exist** — `task` service imports `project.repository` for progress recalculation
- **Team discipline required** — domains must not leak into each other arbitrarily

## Related Decisions
- [ADR 002: Rename Services to Domain Language](002-rename-services-to-domain-language.md)
- [ADR 003: Adopt DDD Folder Structure](003-adopt-ddd-folder-structure.md)
