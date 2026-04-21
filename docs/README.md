# Documentation Index

## Architecture
- [overview.md](architecture/overview.md) — System design, service map, request flows
- [microservices.md](architecture/microservices.md) — Service ownership, shared package, gateway routing
- [flowcharts.md](architecture/flowcharts.md) — Runtime flows for auth, projects, AI, GitHub, routing
- [srs.md](architecture/srs.md) — Software requirements specification
- [decisions/](architecture/decisions/) — Architecture Decision Records (ADRs)

## API
- [reference.md](api/reference.md) — All public routes, request/response contracts

## Database
- [schema.md](database/schema.md) — Full table and column reference (23 tables, 7 domains)
- [erd.md](database/erd.md) — Entity-relationship diagram
- [README.md](database/README.md) — Database hub with links to per-service views
- [per-service/](database/per-service/) — Domain-scoped DB docs (core, ai, git, mcp, gateway)

## AI System
- [context.md](ai/context.md) — Fast start reference: feature flows, edit hotspots, drift notes
- [pipeline.md](ai/pipeline.md) — RAG pipeline, agentic loop, retrieval components
- [tool-registry.md](ai/tool-registry.md) — All 24 tools across 5 categories

## Services
- [services/README.md](services/README.md) — Feature inventory hub per service
- [services/core/README.md](services/core/README.md)
- [services/ai/README.md](services/ai/README.md)
- [services/git/README.md](services/git/README.md)
- [services/mcp/README.md](services/mcp/README.md)
- [services/gateway/README.md](services/gateway/README.md)

## Frontend
- [frontend/FRONTEND-REFERENCE.md](frontend/FRONTEND-REFERENCE.md) — Folder map, route ownership, state flow

## Development
- [development/setup.md](development/setup.md) — Local dev setup, conventions, tooling
- [development/testing.md](development/testing.md) — Automated checks, smoke scripts, manual test matrix

## Review & Assessment
- [review/MICROSERVICES-REVIEW.md](review/MICROSERVICES-REVIEW.md) — Architecture assessment, risks, cleanup priorities

## Archive
- [archive/](archive/) — Phase history, old testing reports, migration notes
