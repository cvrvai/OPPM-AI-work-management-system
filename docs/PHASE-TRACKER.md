# Phase Tracker

Last updated: 2026-04-06

## Purpose

This tracker is a current-state capability map, not a historical wish list.

It answers one question: what is implemented in the repo right now, what is partially implemented, and what still needs hardening.

## Status Legend

- `Completed` means the capability is present in code and reachable through the current product flow.
- `In Progress` means the capability exists but still has contract, UX, or testing gaps.
- `Next` means it is the logical follow-up area after the current implemented surface.

## Current Phase Snapshot

| Phase | Area | Status | Current reality |
|---|---|---|---|
| 1 | Platform foundation | `Completed` | Microservices, shared package, SQLAlchemy async sessions, gateway routing, Redis bootstrap are in place. |
| 2 | Auth and identity | `Completed` | Local JWT auth, refresh tokens, signup, login, me, profile update, signout route all exist. |
| 3 | Workspace management | `Completed` | Workspace CRUD, membership checks, owner-only deletion, and invite preview/accept/resend/revoke flows are live. |
| 4 | Team management | `Completed` | Team now owns member role changes, invite management, and skill management in one surface. |
| 5 | Project management | `Completed` | Project CRUD, project header fields, project detail view, project membership, and project creation wizard exist. |
| 6 | Task execution | `Completed` | Task CRUD, board/list display, assignment, progress, and task daily reports are implemented. |
| 7 | OPPM planning | `Completed` | Objectives, weekly timeline, costs, AI-assisted plan suggestion, and project-level OPPM view are implemented. |
| 8 | Notifications and dashboard | `Completed` | Dashboard stats and notification list/read/unread flows exist. |
| 9 | GitHub integration | `Completed` | GitHub accounts, repo configs, webhook validation, commit ingestion, reports, and recent analyses are implemented. |
| 10 | AI and RAG | `Completed` | Workspace chat, project chat, weekly summary, model config, reindexing, and RAG query route exist. |
| 11 | MCP integration | `Completed` | MCP tool discovery and execution routes are live. |
| 12 | Hardening and contract cleanup | `In Progress` | Docs refresh, schema cleanup, naming normalization, and coverage expansion are still underway. |

## What Is Clearly Working Today

### Platform And Runtime

- frontend + gateway + four backend services are wired
- native and Docker gateway paths both exist
- shared ORM layer is active across services
- health endpoints exist per service

### Auth And Workspace Model

- login, signup, refresh, me, profile update, signout
- workspace creation and retrieval
- workspace member list and role updates
- invite preview, accept, resend, revoke
- per-member skill tracking

### Execution Model

- projects with code, objective summary, budget, planning hours, lead, and scheduling fields
- tasks with status, contribution, assignee, dates, and daily reports
- project members with role-based assignment
- OPPM objectives, timeline, and cost lines

### Intelligence Layer

- workspace and project AI chat
- AI plan suggestion and commit flow
- weekly summary generation
- workspace reindexing
- RAG retrieval pipeline
- commit analysis triggered from Git webhooks
- MCP tools over HTTP

## What Is Partially Complete

### Team And Role UX

The feature exists, but the contract is not fully cleaned up.

Current gap:

- backend workspace responses expose `current_user_role`
- some frontend typing and role checks still assume `role`

### Project Member Contract

The project member flow works, but the public request field name is misleading.

Current gap:

- `user_id` in the request currently carries a workspace member id
- the stored relation is `project_members.member_id`

### Task Assignment Modeling

The product currently behaves as a single-assignee task system.

Current gap:

- `tasks.assignee_id` is the live path
- `task_assignees` still exists in schema and older expectations

### Test Depth

The repo has meaningful validation paths, but coverage is still light relative to the surface area.

Current gap:

- critical flows like invite acceptance, project-member add/remove, and webhook-to-analysis deserve stronger automated tests

## Hardening Work In Flight

This documentation refresh itself is part of the current hardening phase.

Recently completed during this phase:

- docs refreshed against source code instead of stale assumptions
- invite preview schema corrected in `services/core/schemas/workspace.py`
- frontend lint baseline cleaned in Dashboard, Projects, Settings, and OPPMView
- workspace role typing normalized so frontend pages can use `current_user_role` without loose casts
- Projects create and edit dialogs refreshed with wider, calmer planning forms
- Settings simplified around profile, workspace, GitHub, and AI concerns while Team now owns member and invite management
- workspace deletion hardened to be owner-only end-to-end
- `/invite/accept/:token` added as a public alias while `/invites/:token` remains valid
- OPPMView reorganized into a clearer strategic brief, execution matrix, and separate cost section without changing the backend model
- OPPMView further realigned into a spreadsheet-style OPPM sheet with row/column framing, merged metadata rows, a lower X-cross summary area, and a side legend block
- OPPMView redesigned into a classic OPPM template matching oppmi.com with A/B/C priority objectives, auto-fill tasks, SVG status dots, owner badges, X-diagram summary, risk register, cost bar charts, and legend
- Task permissions implemented: lead-only create, assignee-only report, lead-only approve/revoke
- Task report approval and revoke workflow with optimistic UI updates
- ChatPanel inline input bar replaced browser prompt()
- Database schema documentation created (DATABASE-SCHEMA.md)
- frontend and API reference docs refreshed for the Team/Settings ownership split, invite alias route, and owner-only workspace deletion

Current implementation pass:

- OPPM classic template design is complete with priority system and auto-fill tasks
- task permission enforcement is complete end-to-end (backend 403 + frontend gate)
- database schema documentation is comprehensive and up to date
- all docs refreshed to reflect current codebase state

Still worth doing next:

- clean up project member request naming
- decide whether to retire or revive `task_assignees`
- expand end-to-end verification and automated tests

## Suggested Next Phase Focus

If work continues from the current codebase, the highest-value next phase is:

`Phase 13: Contract Cleanup And Product Hardening`

Suggested deliverables:

1. unify backend/frontend field names for workspace role data
2. normalize project member add payload naming
3. settle on one task assignment model
4. add automated coverage for invite, team, task report, and webhook flows
5. keep docs updated as part of each feature PR or release

## Summary

The product is past the prototype stage.

The main domains are implemented. The remaining work is mostly consistency, cleanup, and hardening rather than missing foundational features.
