# Current Phase Tracker

## Task
Add per-service flowcharts in service documentation

## Goal
Ensure each service documentation page has its own flowchart that visually represents how that service processes requests and interacts with other components.

## Plan
- [x] Archive previous tracker to `docs/phase-history/2026-04-20-101242-service-flowcharts-per-service.md`
- [x] Add a dedicated Mermaid flowchart section to `docs/services/core/README.md`
- [x] Add a dedicated Mermaid flowchart section to `docs/services/ai/README.md`
- [x] Add a dedicated Mermaid flowchart section to `docs/services/git/README.md`
- [x] Add a dedicated Mermaid flowchart section to `docs/services/mcp/README.md`
- [x] Add a dedicated Mermaid flowchart section to `docs/services/gateway/README.md`
- [x] Update `docs/services/README.md` to indicate that each service doc includes its own flowchart
- [x] Validate markdown structure and link consistency

## Status
Complete

## Files Expected
Modified:
- `docs/PHASE-TRACKER.md`
- `docs/services/README.md`
- `docs/services/core/README.md`
- `docs/services/ai/README.md`
- `docs/services/git/README.md`
- `docs/services/mcp/README.md`
- `docs/services/gateway/README.md`

Created:
- `docs/phase-history/2026-04-20-101242-service-flowcharts-per-service.md`

## Verification
- Each service doc has one explicit Mermaid flowchart section
- Flowcharts reflect current route ownership and service behavior
- Service hub index remains consistent after updates

## Notes
- This is documentation-only and does not modify runtime code
