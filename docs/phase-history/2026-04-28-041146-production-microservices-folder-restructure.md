# Current Phase Tracker

## Task
Production microservices folder restructure for scalable deployment

## Goal
Split `services/core/` into 5 domain microservices, apply a production-grade standard template
to all 9 services, centralise Alembic migrations, and add deploy/ + monitoring/ infrastructure.
Target: Docker Compose, 100+ concurrent users, production-ready.

## Plan

### Phase 1: Root-level cleanup + infrastructure
- [x] Archive old PHASE-TRACKER.md
- [x] Create this tracker
- [ ] Create `migrations/` at root
- [ ] Create `deploy/` structure (docker/, nginx/, scripts/)
- [ ] Create `monitoring/` structure (prometheus/, grafana/, loki/)
- [ ] Create `tests/e2e/`

### Phase 2: Shared package additions
- [ ] Add `shared/exceptions/base.py`

### Phase 3: New domain services (split from core)
- [ ] services/auth/
- [ ] services/workspace/
- [ ] services/project/
- [ ] services/oppm/
- [ ] services/notification/

### Phase 4: Standard template additions to existing services
- [ ] services/ai/ - middleware, health, exceptions, tests
- [ ] services/git/ - middleware, health, exceptions, tests
- [ ] services/mcp/ - middleware, health, exceptions, tests
- [ ] services/gateway/ - routes.py, circuit_breaker.py, health, middleware

## Status
In progress � Phase 1

## Verification
- [ ] docker build succeeds for each new service
- [ ] GET /health and GET /ready return 200 on all services
- [ ] Full auth flow: POST /api/auth/login ? JWT ? GET /api/v1/workspaces
- [ ] alembic upgrade head runs from root migrations/
- [ ] pytest services/{service}/tests/ passes per service