# OPPM Working Context

This folder is the mandatory first-read workflow gate for the repository.

## Read order

1. Read every file in this `doc/` folder before implementation.
2. Then follow the existing high-signal repo map, including `docs/AI-SYSTEM-CONTEXT.md`, `docs/ARCHITECTURE.md`, and the other files required by repo instructions.
3. Then read `docs/planning/CURRENT_PHASE.md` and `docs/PHASE-TRACKER.md`.

## Workflow mapping

- `docs/planning/` holds project-level phase planning.
- `docs/PHASE-TRACKER.md` remains the active task-level tracker.
- `docs/history/` stores project phase summaries.
- `docs/phase-history/` stores archived task trackers.
- `docs/architecture/`, `docs/decisions/`, and `docs/tasks/` hold durable cross-task memory.

## Repository shape

- `frontend/`, `gateway/`, `services/`, and `shared/` define the main runtime surfaces.
- `deploy/`, `monitoring/`, `scripts/`, and `tests/` support operations and validation.
- Existing `docs/` directories already hold system, service, feature, and runbook documentation.