# ADR 004: Remove Dead Microservices

## Status
Accepted (2026-05-01)

## Context
The `services/` folder contained 9 subfolders but only 5 were operational:

| Folder | Port | Status |
|---|---|---|
| `core` | 8000 | Active — routed by gateway |
| `ai` | 8001 | Active — routed by gateway |
| `git` | 8002 | Active — routed by gateway |
| `mcp` | 8003 | Active — routed by gateway |
| `gateway` | 8080 | Active — routed by gateway |
| `auth` | 8004 | **Dead** — not in gateway routing, not in docker-compose |
| `workspace` | 8005 | **Dead** — not in gateway routing, not in docker-compose |
| `project` | 8006 | **Dead** — not in gateway routing, not in docker-compose |
| `notification` | 8008 | **Dead** — not in gateway routing, not in docker-compose |
| `secrets` | — | **Empty** — only `.gitkeep` |

These dead services were incomplete extractions — someone started splitting `core` into finer services but never updated the gateway, nginx, or docker-compose to route to them. Meanwhile `core` still contained all the same code.

## Decision
Remove the dead services entirely:

- Delete `services/auth/`
- Delete `services/workspace/` (the old unused one)
- Delete `services/project/`
- Delete `services/notification/`
- Delete `services/secrets/`

Consolidate all business logic into `services/workspace/` (the renamed `core`).

## Consequences

### Positive
- **No confusion** — new developers don't wonder why there are 9 services but only 5 run
- **Less ops overhead** — 4 business services to deploy and monitor instead of 8
- **Single source of truth** — auth, workspace, project, task, OPPM, notifications all in one place

### Negative
- **Lost extraction work** — the dead services had some copied code (main.py, config.py, Dockerfile)
- **If we want to split later** — we start from scratch, not from the dead services

## Related Decisions
- [ADR 001: Use Modular Monolith with DDD Domains](001-use-modular-monolith.md)
- [ADR 002: Rename Services to Domain Language](002-rename-services-to-domain-language.md)
