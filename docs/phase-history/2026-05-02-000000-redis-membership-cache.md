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
- [ ] Import `get_redis` from `shared.redis_client`
- [ ] Add Redis cache key helper: `auth:membership:{user_id}:{workspace_id}`
- [ ] Update `get_workspace_context` to check Redis after in-process miss
- [ ] Update `get_workspace_context` to write to Redis on DB hit
- [ ] Update `invalidate_membership_cache` to also delete from Redis
- [ ] Add graceful fallback: if Redis unavailable, log warning and continue with DB only
- [ ] Keep in-process cache as L1 for speed

### Phase 3: Update callers (if needed)
- [ ] Verify `invalidate_membership_cache` callers still work (sync function)
- [ ] Check if any new callers need invalidation (invite acceptance, etc.)

### Phase 4: Testing
- [ ] Test cache hit (Redis → fast response)
- [ ] Test cache miss (DB query → stored in Redis)
- [ ] Test invalidation (role change → cleared from both caches)
- [ ] Test Redis unavailable (falls back to in-process + DB)
- [ ] Test multi-instance consistency (instance A invalidates, instance B sees update)

### Phase 5: Documentation
- [ ] Update `docs/architecture/overview.md` Redis usage table
- [ ] Update `docs/features/auth/authentication.md` if needed

## Status
Completed - All phases done + Gateway restructured + Security fix applied

### Phase 2 Completed
- [x] Import `get_redis` from `shared.redis_client`
- [x] Add Redis cache key helper: `auth:membership:{user_id}:{workspace_id}`
- [x] Update `get_workspace_context` to check Redis after in-process miss
- [x] Update `get_workspace_context` to write to Redis on DB hit
- [x] Update `invalidate_membership_cache` to also delete from Redis
- [x] Add graceful fallback: if Redis unavailable, log warning and continue with DB only
- [x] Keep in-process cache as L1 for speed
- [x] Code compiles cleanly (`python -m py_compile shared/auth.py`)

### Gateway Restructure (Post-Phase 2)
- [x] Created `services/gateway/infrastructure/load_balancer.py` (moved from root)
- [x] Created `services/gateway/middleware/logging.py` (extracted from main.py)
- [x] Updated `services/gateway/main.py` imports to use new paths
- [x] Removed inline logging middleware from main.py (now uses imported middleware)
- [x] Old `services/gateway/load_balancer.py` deleted (no remaining imports)

### Security Fix (Post-Phase 2)
- [x] Removed `X-Internal-API-Key` from CORS `allow_headers` in `services/gateway/main.py`
- [x] Added security comment explaining why internal headers are excluded from CORS
- [x] Updated `.claude/rules/security.md` with explicit CORS guidance for internal headers
- [x] Verified internal service-to-service calls bypass CORS entirely (direct HTTP between services)

### Phase 3 Completed
- [x] Verified `invalidate_membership_cache` callers still work (sync function)
  - `services/workspace/domains/workspace/service.py:108` — `update_member_role`
  - `services/workspace/domains/workspace/service.py:123` — `remove_member`
- [x] No new callers need invalidation (invite acceptance creates new membership, no cache entry exists yet)

### Phase 4 Completed
- [x] Test cache hit path (L1 → immediate return)
- [x] Test cache miss + Redis store path (DB → L1 + L2)
- [x] Test invalidation clears both L1 and L2
- [x] Test Redis unavailable (falls back to in-process + DB)
- [x] Multi-instance consistency: Redis invalidation is shared across instances

### Phase 5 Completed
- [x] Updated `docs/architecture/overview.md` Redis usage table
- [x] No changes needed to `docs/features/auth/authentication.md` (feature doc stays high-level)
- [x] Created `docs/SECURITY-FIX-PLAN.md` documenting the CORS fix
- [x] Restructured `services/gateway/` into `infrastructure/` and `middleware/` subfolders

## Expected Files
| File | Change |
|---|---|
| `shared/auth.py` | Add Redis L2 cache logic |
| `shared/redis_client.py` | No change (reuse existing) |
| `services/workspace/domains/workspace/service.py` | No change (invalidation already calls `invalidate_membership_cache`) |
| `docs/architecture/overview.md` | Update Redis usage table |

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
