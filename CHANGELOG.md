# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.0.0] — 2026-04-21

### Added
- Multi-tenant workspace architecture with role-based access control (owner / admin / member / viewer)
- OPPM board: objectives with weekly status dots, inline editing, RAG risk tracking, cost bar charts
- AI chat with context-aware RAG over project data; pluggable LLM (Ollama, OpenAI, Anthropic, Kimi)
- GitHub integration: link repos to projects, auto-analyse commits against OPPM objectives
- Weekly AI summary: structured status report generated from live project data
- Agile board (Kanban), Waterfall view (Gantt), and OPPM methodology support
- MCP (Model Context Protocol) service for tool-based AI interactions
- GraphQL endpoint on AI service
- Semantic similarity cache (Redis, cosine ≥ 0.92, 5 min TTL) for RAG results
- Input guardrails (injection detection) and output guardrails (sensitive data scrub)
- TAOR agentic loop with max 7 iterations and low-confidence requery fallback
- Enterprise folder structure: `apps/`, `packages/shared/`, `infrastructure/nginx/`
- CI/CD pipeline via `.github/workflows/ci.yml`

### Changed
- Repository restructured from `services/` → `apps/` and `shared/` → `packages/shared/`
- Documentation reorganized into `docs/architecture/`, `docs/api/`, `docs/database/`, `docs/development/`
- Nginx gateway config moved to `infrastructure/nginx/`

## [1.0.0] — 2026-03-01

### Added
- Initial OPPM monolith with core project management features
- PostgreSQL schema with workspace-scoped multi-tenancy
- React frontend with TanStack Query and Zustand
