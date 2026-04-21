# Workspace Guidelines

## Documentation First

- For system summaries, feature updates, or schema changes, read `docs/AI-SYSTEM-CONTEXT.md` first as the high-signal repository map.
- For every task, read the project documents that are relevant before making claims or edits.
- Start from `CLAUDE.md`, `README.md`, `DEVELOPMENT.md`, and the relevant files under `docs/`.
- Use `docs/AI-SYSTEM-CONTEXT.md` to narrow the files you need, then verify the relevant implementation in code before changing behavior or contracts.
- When the user asks what the system has, summarize the verified system purpose, main services, frontend, backend, auth and tenancy model, database domains, integrations, and any documentation drift.
- When documentation needs to be updated, verify facts against the codebase first and prefer code over outdated docs.
- Documentation updates may target any documentation-like markdown file in the repository when relevant to the request.
- Keep documentation edits focused and explicit; do not rewrite broad sections unless the structure itself is wrong.

## Phase Tracking

- Before starting a new implementation or documentation task with edits, create `docs/PHASE-TRACKER.md` for that task.
- If `docs/PHASE-TRACKER.md` already exists from an older task, move it into `docs/phase-history/` with a `YYYY-MM-DD-HHMMSS-task-slug.md` filename before creating the new tracker.
- Do not start editing code or docs for a new task until the current phase tracker exists.
- Keep the current tracker updated with the task summary, goal, plan, status, expected files, and verification notes.
- Use `docs/phase-history/` only for archived task trackers. Do not overwrite archived files.

## Preferred Workflow

- Use the `Phase Tracker Implementer` agent for tasks that should strictly follow the phase-tracker workflow.
- Use the Documentation Maintainer agent or the `documentation-maintainer` skill for larger documentation or system-summary tasks.
- Call out mismatches between documents and implementation instead of silently choosing one version.