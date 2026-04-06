# Microservices Review

Last updated: 2026-04-06

## Executive Summary

The current backend architecture is a workable and coherent microservices split built around a shared PostgreSQL data model and a thin gateway layer.

What is solid:

- service responsibilities are understandable
- the shared ORM package prevents schema duplication across services
- the core service owns the main business workflow cleanly
- AI, GitHub, and MCP capabilities are separated instead of being bolted directly into core
- the Python gateway mirrors the same routing intent as the nginx gateway

What still needs attention:

- a few public field names do not match the underlying relational identifiers cleanly
- gateway rules exist in two places and can drift
- some frontend types still lag behind backend response names
- the schema carries both current and legacy task assignment patterns
- automated coverage is still light relative to the feature surface

Overall assessment:

- architecture direction: good
- implementation maturity: medium
- documentation accuracy after this refresh: good
- remaining hardening work: moderate

## What Was Verified In Code

This review is based on the current source, not on older design notes.

Confirmed facts:

- auth uses locally validated HS256 JWTs in `shared/auth.py`
- workspace authorization resolves through `workspace_members`
- the core service mounts both `/api/auth/*` and `/api/v1/*`
- AI, Git, and MCP services expose their own `/api/v1/*` route groups
- the AI service also exposes `/internal/analyze-commits` protected by `X-Internal-API-Key`
- `shared/models/` is the active ORM source of truth
- migrations are owned by `services/core/alembic/`
- Redis is optional support infrastructure, not the source of truth

## Service Topology Assessment

### Core Service

Assessment: strong

Why:

- most business rules live where they should
- the route surface is clear
- repositories and services are separated reasonably well
- it is the correct place for migrations and workspace authorization-driven CRUD

### AI Service

Assessment: strong but integration-heavy

Why:

- AI responsibilities are sensibly isolated
- chat, plan generation, reindexing, and retrieval belong together
- the service already contains a real internal-only route for commit analysis

Risk area:

- this service touches many cross-cutting concepts, so schema or prompt drift can surface here first

### Git Service

Assessment: good

Why:

- GitHub account, repo, webhook, and commit flows are grouped correctly
- webhook processing is split into fast acknowledge plus background work
- handoff to AI is explicit instead of hidden in a monolith callback

Risk area:

- webhook and repo configuration security must stay tight because secrets live here

### MCP Service

Assessment: clean and focused

Why:

- service boundary is narrow
- tool registry pattern is straightforward
- it keeps tool execution separate from the AI service HTTP surface

### Gateway Layer

Assessment: acceptable but fragile

Why:

- route ownership is clear in code
- health-aware load balancing in native dev is useful

Risk area:

- duplicated route tables in Python and nginx must be maintained manually

## Data Architecture Assessment

Assessment: strong foundation with a few naming mismatches

What is working well:

- shared SQLAlchemy models reduce service duplication
- workspace-scoped modeling is consistent across the main domains
- project, task, OPPM, Git, and AI tables fit together sensibly
- audit and retrieval are cross-cutting but still sit in understandable places

What needs cleanup:

- `project_members.member_id` is correct relationally, but the public add-member payload still calls the field `user_id`
- workspace role data is exposed as `current_user_role` in backend responses, while parts of the frontend still type it as `role`
- both `tasks.assignee_id` and `task_assignees` exist, but the main product flow uses the single-assignee path

## Auth And Security Assessment

Assessment: adequate for current architecture, with a few follow-up items

Strengths:

- local JWT validation is explicit and understandable
- workspace RBAC is centralized in `shared/auth.py`
- internal service routes use a separate API key mechanism
- GitHub webhook validation uses HMAC SHA-256

Follow-up items:

- keep token logging redacted only
- verify signout blacklisting path end-to-end under real traffic
- keep sensitive GitHub and AI credentials out of all API responses

## Frontend/Backend Contract Review

This is the main area where polish is still needed.

Observed contract issues:

1. Workspace role naming drift.
   The backend returns `current_user_role`, but some frontend types and role checks still expect `role`.

2. Project member identifier naming drift.
   The project member add route accepts a field named `user_id`, but the working value is a workspace member id.

3. Task assignment model duplication.
   The database still includes `task_assignees`, but the current UI and route model use `tasks.assignee_id`.

These are not architecture-breaking problems, but they are exactly the kind of small inconsistencies that create bugs during feature work.

## Code Health Review

What looks healthy:

- service ownership is easy to trace from router to service to repository
- the shared package gives the codebase a real center of gravity
- the main route groups are not deeply tangled together
- the docs can now be aligned to source without inventing missing layers

What still increases maintenance cost:

- duplicated gateway routing logic
- partial type drift between frontend and backend
- legacy artifacts remaining in schema and contracts
- limited automated tests for the total feature surface

## Recent Corrections During This Review

One real schema contract issue was corrected while preparing this documentation refresh:

- `services/core/schemas/workspace.py` was fixed so `InvitePreviewResponse` now carries `accepted_at`, `member_count`, `is_expired`, and `is_accepted`
- those fields were removed from `MemberSkillCreate`, where they had been attached incorrectly

That fix matters because the invite preview route and the Team/skills feature now have the correct schema separation.

## Recommended Next Actions

Priority order:

1. normalize workspace role response naming between backend and frontend
2. rename or wrap the project member add payload so the public field matches the real identifier type
3. decide whether `task_assignees` is still strategic or should be retired from the live path
4. add automated tests around invites, project membership, task reports/approvals, and webhook-to-analysis flow
5. keep Python gateway and nginx gateway routing rules synchronized whenever routes change

## Recent Improvements (2026-04-06)

- task permission enforcement: lead-only create, assignee-only reports, lead-only approval
- OPPM view redesigned to classic template with A/B/C priority, auto-fill tasks, SVG status dots
- `priority VARCHAR(1)` added to `oppm_objectives` table
- OPPM serialization bug fixed (UUID/datetime objects now properly converted for JSON responses)
- cost summary serialization fixed (`_row_to_dict` helper used consistently)
- comprehensive database schema documentation created (`docs/DATABASE-SCHEMA.md`)

## Overall Conclusion

The system is in better shape than the stale docs suggested.

This is not a fake microservices split. It is a real service decomposition with a sensible shared data layer and clear domain boundaries.

The remaining issues are mostly contract cleanup and hardening work, not foundational architecture failure. That is a good place to be.
