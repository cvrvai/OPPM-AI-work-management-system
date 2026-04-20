# Current Phase Tracker

## Task
Create service documentation hub for feature inventory and future upgrade planning

## Goal
Add a dedicated `docs/services/` documentation hub with one section per service that lists current features, owned routes, dependencies, and change-impact guidance so future updates (such as Graph API or GraphRAG adoption) are easier and safer.

## Plan
- [x] Archive previous tracker to `docs/phase-history/2026-04-20-095633-service-doc-hub-plan.md`
- [x] Define `docs/services` structure and per-service doc template
- [x] Verify service feature ownership from code
- [x] Create `docs/services/README.md` service index
- [x] Create per-service docs for core, ai, git, mcp, and gateway
- [x] Add AI evolution section (current RAG vs Graph API vs GraphRAG vs hybrid path)
- [x] Update cross-links from root docs to the new service hub
- [x] Validate internal links and coverage

## Status
Complete

## Files Expected
Created:
- `docs/services/README.md`
- `docs/services/core/README.md`
- `docs/services/ai/README.md`
- `docs/services/git/README.md`
- `docs/services/mcp/README.md`
- `docs/services/gateway/README.md`

Modified:
- `docs/PHASE-TRACKER.md`
- `docs/ARCHITECTURE.md`
- `docs/MICROSERVICES-REFERENCE.md`
- `docs/AI-SYSTEM-CONTEXT.md`
- `README.md`
- `docs/phase-history/2026-04-20-095633-service-doc-hub-plan.md`

## Verification
- All active backend services have service-level docs in `docs/services/`
- AI service doc includes explicit upgrade paths for Graph API and GraphRAG
- Service docs list current routes, features, dependencies, and update impact points
- Root docs link to the new service hub without breaking existing required doc paths

## Notes
- Required root docs remain in place for instruction and tooling compatibility
- `docs/services/` is additive and intended as the feature-level maintenance map
- Existing `docs/phase-history/*` entries intentionally preserve historical paths and were not rewritten
