---
name: documentation-maintainer
description: 'Read project documentation, summarize what the system has, and update docs to match the current codebase. Use for README updates, architecture refreshes, API documentation, onboarding summaries, documentation drift checks, and requests like read the docs, explain this system, or update the documents.'
argument-hint: 'Describe what documentation to read or update, and any area to focus on'
---

# Documentation Maintainer

Use this skill for documentation-first work. Start by reading the core project documents, then explain what the system currently contains before making any documentation edits.

## When to Use

- The user asks to read documentation and explain the system.
- The user asks what the system has, how it is structured, or what services and features exist.
- The user asks to update README files, architecture docs, API docs, or implementation notes.
- The user wants a documentation drift check between docs and code.
- The user wants onboarding or project summary material derived from the repository.

## Default Reading Order

Read the high-signal project documents first.

1. `CLAUDE.md`
2. `README.md`
3. `DEVELOPMENT.md`
4. `docs/ARCHITECTURE.md`
5. `docs/API-REFERENCE.md`
6. `docs/DATABASE-SCHEMA.md`
7. `docs/frontend/FRONTEND-REFERENCE.md`
8. `docs/MICROSERVICES-REFERENCE.md`
9. Any area-specific document directly related to the request

Then verify the current implementation from code before stating facts or updating docs.

## Code Sources of Truth

When documentation and code differ, prefer the code and record the mismatch.

- Backend entry points: `services/*/main.py`, `services/core/main.py`, `services/gateway/main.py`
- Backend API surface: `services/*/routers/`, `services/core/routers/`, `services/*/schemas/`
- Business logic: `services/*/services/`, `services/core/services/`
- Shared platform behavior: `shared/auth.py`, `shared/database.py`, `shared/models/`
- Frontend stack and routes: `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/pages/`, `frontend/src/lib/api.ts`
- Deployment/runtime shape: `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.microservices.yml`, `start_*.ps1`

## Procedure

1. Determine the scope.
   - If the user asked to explain the system, produce a system inventory summary first.
   - If the user asked to update docs, still produce a short current-state summary before editing.
   - If the request targets one subsystem, narrow both the documents and the code review to that area.

2. Read the relevant documents before editing anything.
   - Start with the default reading order.
   - Add focused documents for the requested area.

3. Verify the current implementation from code.
   - Check the files that are the source of truth for the requested area.
   - Do not copy stale statements from older docs into newer docs.

4. Summarize what the system has.
   - State the product purpose in one short paragraph.
   - List the major services or applications in the repository.
   - State the frontend stack and major frontend areas.
   - State the backend stack, auth model, and multi-tenant or workspace model.
   - State the main data domains and integrations if they are relevant.
   - Call out any verified drift between docs and code.

5. Update documentation only after the summary is grounded in the codebase.
   - Edit the smallest set of files that fully resolves the request.
   - Preserve existing terminology and structure unless the current structure is part of the problem.
   - If a fact cannot be verified from code, say so instead of inventing details.

6. Close with verification.
   - Mention which documents were updated.
   - Mention whether the result was checked against code, tests, or both.
   - List any unresolved ambiguity or stale areas that still need human confirmation.

## Required Output for "What Does This System Have?"

When the user asks what the system has, include these sections in the response:

1. System purpose
2. Main applications and services
3. Frontend structure
4. Backend structure
5. Auth, database, and tenancy model
6. Key integrations or platform capabilities
7. Documentation drift or uncertainty

Keep the answer concise, but make sure it describes the actual repository rather than generic architecture language.

## Quality Checks

Before finishing, confirm that:

- The summary reflects the current repository, not only old docs.
- Documentation updates are backed by code or clearly marked assumptions.
- Any mismatch between docs and implementation is called out explicitly.
- The response explains what the system has, not just what files exist.
- The user can tell which parts were verified and which parts remain uncertain.

## Example Prompts

- `Use documentation-maintainer to explain what this system has.`
- `Read the docs and refresh README.md so it matches the current architecture.`
- `Compare the API documentation with the current FastAPI routes and update the docs.`
- `Summarize the frontend, backend, and data model from the project documents and code.`
