# Current Phase Tracker

## Task
AI architecture alignment and gateway route consistency

## Goal
Bring the documented AI architecture back in line with the running code, fix the gateway path needed for internal commit analysis in native and proxied setups, and close the auth/capability drift around workspace chat tool execution.

## Plan
- [x] Archive the previous phase tracker to `docs/phase-history/2026-04-10-092708-ai-architecture-alignment.md`
- [x] Add explicit gateway support for `/internal/analyze-commits` in both `services/gateway/main.py` and `gateway/nginx.conf`
- [x] Align workspace chat auth and capabilities with the implemented tool-enabled behavior in `services/ai/routers/v1/ai_chat.py`
- [x] Update the core architecture docs to reflect actual AI ownership, route boundaries, tool categories, and TAOR loop limits
- [x] Refresh supporting AI/microservice docs and diagrams that still claim 21 tools or 5 iterations
- [x] Verify modified files and note any remaining follow-up items

## Status
Complete

## Files Expected
Modified:
- `services/gateway/main.py`
- `gateway/nginx.conf`
- `services/ai/routers/v1/ai_chat.py`
- `docs/ARCHITECTURE.md`
- `docs/AI-SYSTEM-CONTEXT.md`
- `docs/API-REFERENCE.md`
- `docs/AI-PIPELINE-REFERENCE.md`
- `docs/TOOL-REGISTRY-REFERENCE.md`
- `docs/MICROSERVICES-REFERENCE.md`
- `docs/MICROSERVICES-REVIEW.md`
- `docs/FLOWCHARTS.md`

Created:
- `docs/phase-history/2026-04-10-092708-ai-architecture-alignment.md`

## Verification
- Gateway route tables in Python and nginx both forward `/internal/analyze-commits` to the AI service
- Workspace chat route and capabilities endpoint no longer disagree about tool execution
- Main docs reflect 24 tools across 5 categories and a 7-iteration TAOR limit
- AI ownership is described as real route ownership plus shared-database tool writes, not just advisory helpers

## Notes
- The AI service directly owns both workspace and project AI endpoints under `services/ai/routers/v1/ai_chat.py`
- The current runtime exposes a richer AI surface than the docs described: workspace chat, project chat, suggest-plan, weekly summary, parse-file, OPPM fill, OPPM extract, feedback, RAG, and internal commit analysis
- Workspace chat currently runs the TAOR loop with the full tool registry; the previous docs and capabilities response were stale
- Native development guidance says service-to-service calls can go through the gateway; the missing `/internal/analyze-commits` proxy path was preventing the AI analysis route from matching that model
- Follow-up decision outside this pass: if viewers should keep a read-only workspace chat, split the route behavior by role instead of using a single write-gated workspace chat endpoint
