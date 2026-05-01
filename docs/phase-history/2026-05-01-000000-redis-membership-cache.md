# Current Phase Tracker

## Task
Move workspace membership cache from in-process Python dict to Redis for shared consistency across instances.

## Goal
- Eliminate stale role data in multi-instance deployments
- Keep fast in-process cache as L1, add Redis as L2 shared cache
- Maintain graceful fallback if Redis is unavailable
- Preserve existing invalidation behavior

## Plan

### Phase 1: Archive old tracker
- [x] Move current `docs/PHASE-TRACKER.md` to `docs/phase-history/2026-05-01-000000-microservice-rename.md`
- [x] Create new tracker for Redis membership cache

### Phase 2: Update `shared/auth.py`
- [x] Import `get_redis` from `shared.redis_client`
- [x] Add Redis cache key helper: `auth:membership:{user_id}:{workspace_id}`
- [x] Update `get_workspace_context` to check Redis after in-process miss
- [x] Update `get_workspace_context` to write to Redis on DB hit
- [x] Update `invalidate_membership_cache` to also delete from Redis
- [x] Add graceful fallback: if Redis unavailable, log warning and continue with DB only
- [x] Keep in-process cache as L1 for speed

### Phase 3: Update callers (if needed)
- [x] Verify `invalidate_membership_cache` callers still work (sync function)
- [x] Check if any new callers need invalidation (invite acceptance, etc.)

### Phase 4: Testing
- [x] Test cache hit (Redis → fast response)
- [x] Test cache miss (DB query → stored in Redis)
- [x] Test invalidation (role change → cleared from both caches)
- [x] Test Redis unavailable (falls back to in-process + DB)
- [x] Test multi-instance consistency (instance A invalidates, instance B sees update)

### Phase 5: Documentation
- [x] Update `docs/architecture/overview.md` Redis usage table
- [x] Update `docs/features/auth/authentication.md` if needed

### Phase 6: Gateway Restructure
- [x] Created `services/gateway/infrastructure/load_balancer.py`
- [x] Created `services/gateway/middleware/logging.py`
- [x] Updated `services/gateway/main.py` imports
- [x] Removed inline logging middleware from main.py

### Phase 7: Security Fix
- [x] Removed `X-Internal-API-Key` from CORS `allow_headers`
- [x] Added security comment in main.py
- [x] Updated `.claude/rules/security.md`
- [x] Verified internal calls bypass CORS

## Status
Completed - All phases done + Gateway restructured + Security fix applied

## Expected Files
| File | Change |
|---|---|
| `shared/auth.py` | Add Redis L2 cache logic |
| `shared/redis_client.py` | No change (reuse existing) |
| `services/workspace/domains/workspace/service.py` | No change (invalidation already calls `invalidate_membership_cache`) |
| `docs/architecture/overview.md` | Update Redis usage table |
| `services/gateway/infrastructure/load_balancer.py` | Moved from root |
| `services/gateway/middleware/logging.py` | Extracted from main.py |
| `services/gateway/main.py` | Updated imports, removed inline middleware |
| `docs/SECURITY-FIX-PLAN.md` | Documented CORS fix |

## Verification
- [x] `python -m py_compile shared/auth.py`
- [x] `python -m py_compile services/gateway/main.py`
- [x] Role change reflects immediately across instances
- [x] Redis down → app still works with DB fallback

## Notes
- Cache TTL: keep 60s (same as current)
- Redis key prefix: `auth:membership:`
- Serialization: JSON string `{role, member_id, expires_at}`
- Graceful degradation: log warning, do not fail request
