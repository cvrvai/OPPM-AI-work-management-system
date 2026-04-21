# Current Phase Tracker

## Task
Microservice documentation organization with function and interaction charts

## Goal
Reorganize microservice documentation so readers can quickly understand service boundaries, function ownership, request lifecycles, and cross-service interactions through clearer flowcharts and summary tables.

## Plan
- [x] Archive the previous tracker to `docs/phase-history/2026-04-20-080224-microservice-doc-flowcharts.md`
- [x] Verify current service boundaries and route ownership from code (`services/*/main.py`, routers, gateway route tables, shared auth)
- [x] Reorganize `docs/FLOWCHARTS.md` with clearer grouped sections (system map, service interaction charts, function-level flows)
- [x] Expand `docs/MICROSERVICES-REFERENCE.md` with a function ownership matrix and chart navigation links
- [x] Update architecture index links if needed and ensure docs are internally cross-linked (no new doc file created; existing index links remain valid)
- [x] Review for doc/code drift and capture remaining caveats explicitly

## Status
Complete

## Files Expected
Modified:
- `docs/FLOWCHARTS.md`
- `docs/MICROSERVICES-REFERENCE.md`
- `docs/PHASE-TRACKER.md`

Created:
- `docs/phase-history/2026-04-20-080224-microservice-doc-flowcharts.md`

## Verification
- Charts reflect current route ownership in `services/gateway/main.py` and `gateway/nginx.conf`
- Function flow descriptions align to router → service → repository structure in service code
- Cross-service chart explicitly includes Git webhook to AI internal analysis flow
- Documentation clearly states workspace-scoped auth and shared database boundary

## Notes
- Verified runtime services: core, ai, git, mcp, python gateway, nginx gateway, shared package
- Current notable caveats remain: gateway route duplication risk, role/identifier naming drift in some contracts
- Added grouped charts for service interaction, router-to-data lifecycle, and per-service function flow
