# Current Phase Tracker

## Task
Organize docs into functional subfolders

## Goal
Create functional subfolders inside `docs/` and relocate function-specific documentation files so the docs structure is easier to navigate.

## Plan
- [x] Archive prior tracker to `docs/phase-history/2026-04-20-083417-docs-subfolder-organization.md`
- [x] Identify safe move candidates that do not break required root-path docs used by project instructions
- [x] Create functional folders and move target docs into them
- [x] Update all affected links and references in active docs and README
- [x] Validate docs directory layout and cross-links

## Status
Complete

## Files Expected
Modified:
- `docs/PHASE-TRACKER.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/AI-SYSTEM-CONTEXT.md`
- `docs/SRS.md`
- `.github/skills/documentation-maintainer/SKILL.md`

Moved:
- `docs/AI-PIPELINE-REFERENCE.md` -> `docs/ai/AI-PIPELINE-REFERENCE.md`
- `docs/TOOL-REGISTRY-REFERENCE.md` -> `docs/ai/TOOL-REGISTRY-REFERENCE.md`
- `docs/FRONTEND-REFERENCE.md` -> `docs/frontend/FRONTEND-REFERENCE.md`
- `docs/MICROSERVICES-REVIEW.md` -> `docs/review/MICROSERVICES-REVIEW.md`
- `docs/OPPM-ARCHITECTURE.md` -> `docs/oppm/OPPM-ARCHITECTURE.md`

## Verification
- Functional subfolders exist and moved docs are present in their new locations
- Active references point to new file paths
- Required root-path core docs remain in place for tooling compatibility

## Notes
- Core files referenced directly by project instructions are intentionally kept at `docs/` root
- Functional subfolders added: `docs/ai`, `docs/frontend`, `docs/review`, `docs/oppm`
