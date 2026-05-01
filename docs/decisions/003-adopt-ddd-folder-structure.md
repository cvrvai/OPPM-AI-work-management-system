# ADR 003: Adopt DDD Folder Structure

## Status
Accepted (2026-05-01)

## Context
The original structure organized code by **technical role** (layered architecture):

```
services/core/
  ├── routers/        ← HTTP handlers
  ├── services/       ← business logic
  ├── repositories/   ← database access
  ├── schemas/        ← Pydantic models
  └── middleware/     ← cross-cutting
```

Problems:
- To understand "projects", a developer opens 4 different folders
- No clear ownership — `services/project_service.py` is far from `repositories/project_repo.py`
- Hard to extract — extracting `project` to its own service means hunting across folders
- Not DDD — organized by technical layer, not business capability

We considered:
1. **Vertical slices** — flat folders per domain
2. **Clean Architecture** — strict domain/application/infrastructure layers
3. **Hybrid DDD** — `domains/` folder with self-contained modules

## Decision
Adopt **Option 3: Hybrid DDD with `domains/` folder**.

```
services/workspace/
  ├── domains/
  │   ├── auth/         ← router.py, service.py, repository.py, schemas.py
  │   ├── workspace/    ← router.py, service.py, repository.py, schemas.py
  │   ├── project/      ← router.py, service.py, repository.py, schemas.py
  │   ├── task/         ← router.py, service.py, repository.py, schemas.py
  │   └── ...
  ├── infrastructure/   # external clients (email, sheets, export)
  ├── middleware/       # auth, logging, rate limit
  └── main.py           # mounts all domain routers
```

Each domain is self-contained. Cross-domain references are explicit (e.g., `domains.task.repository` imports `domains.project.repository` for progress recalculation).

## Consequences

### Positive
- **Maximum cohesion** — everything about "projects" is in one folder
- **Extractable** — copy `domains/project/` to `services/project/` when it outgrows the monolith
- **FastAPI-friendly** — SQLAlchemy models live with the service and router
- **Not over-engineered** — no ports/adapters ceremony

### Negative
- **More nesting** — 3 levels deep (`domains/project/router.py` vs `routers/projects.py`)
- **Import paths longer** — `from domains.project.service import create_project`
- **Cross-domain imports** — task → project repository for progress recalculation

## Related Decisions
- [ADR 001: Use Modular Monolith with DDD Domains](001-use-modular-monolith.md)
- [ADR 002: Rename Services to Domain Language](002-rename-services-to-domain-language.md)
