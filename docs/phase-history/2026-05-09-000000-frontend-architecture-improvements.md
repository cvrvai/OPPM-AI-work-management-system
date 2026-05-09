# Phase Tracker

## Task
Frontend Architecture Improvements — Address 7 identified weaknesses in the React frontend.

## Goal
Incrementally improve the frontend architecture by adding error boundaries, code splitting, schema validation, optimistic updates, request cancellation, normalized cache patterns, and service worker support.

## Plan

### Phase 1: Error Boundaries (Foundation — Safety First)
**Priority: High | Estimated: 2-3 hours**

1. Create `components/ErrorBoundary.tsx` — class component with `componentDidCatch`
2. Wrap the app shell in `App.tsx`:
   - Top-level boundary around `<Layout />`
   - Secondary boundary around `<ChatPanel />` (isolated failures)
3. Create `pages/ErrorFallback.tsx` — friendly error UI with "Reload" and "Go Home" actions
4. Add error logging hook: `hooks/useErrorLogger.ts` — sends to console (future: Sentry)

**Files Expected:**
- `frontend/src/components/ErrorBoundary.tsx`
- `frontend/src/pages/ErrorFallback.tsx`
- `frontend/src/hooks/useErrorLogger.ts`
- `frontend/src/App.tsx` (wrap routes)

**Verification:**
- [ ] Throw test error in Dashboard → caught by boundary, shows fallback UI
- [ ] Throw error in ChatPanel → Chat crashes but rest of app stays usable
- [ ] Build passes with zero errors

---

### Phase 2: Route-Level Code Splitting
**Priority: High | Estimated: 3-4 hours**

1. Convert all page imports in `App.tsx` to `React.lazy()`:
   ```ts
   const Dashboard = lazy(() => import('@/pages/Dashboard'))
   ```
2. Add `components/SuspenseFallback.tsx` — minimal spinner for route transitions
3. Wrap `<Outlet />` in `Layout.tsx` with `<Suspense>`
4. Verify chunk output in `dist/assets/` after build

**Files Expected:**
- `frontend/src/App.tsx` (lazy imports)
- `frontend/src/components/SuspenseFallback.tsx`
- `frontend/src/components/layout/Layout.tsx` (Suspense wrapper)

**Verification:**
- [ ] Build produces multiple `.js` chunks (not just `index-*.js`)
- [ ] Navigate between routes → brief fallback spinner, then page loads
- [ ] No hydration mismatches or flickering

---

### Phase 3: Runtime Schema Validation (Zod)
**Priority: Medium | Estimated: 4-5 hours**

1. Install `zod` dependency
2. Create `schemas/` directory with domain schemas:
   - `schemas/workspace.ts` — `WorkspaceSchema`, `WorkspaceMemberSchema`
   - `schemas/project.ts` — `ProjectSchema`, `TaskSchema`
   - `schemas/ai.ts` — `ChatMessageSchema`, `CommitAnalysisSchema`
3. Create `lib/validatedApi.ts` — wrapper around `api.ts` that `.parse()`s responses:
   ```ts
   export const validatedApi = {
     get: <T extends z.ZodType>(path: string, schema: T) =>
       api.get<z.infer<T>>(path).then(schema.parse)
   }
   ```
4. Migrate one page end-to-end (e.g., `Dashboard.tsx`) as proof of concept
5. Gradually migrate remaining pages in follow-up PRs

**Files Expected:**
- `frontend/src/schemas/workspace.ts`
- `frontend/src/schemas/project.ts`
- `frontend/src/schemas/ai.ts`
- `frontend/src/lib/validatedApi.ts`
- `frontend/src/pages/Dashboard.tsx` (refactored to use validatedApi)

**Verification:**
- [ ] Dashboard loads with validated schemas
- [ ] Intentionally malformed API response → Zod error in console, boundary catches it
- [ ] Build passes, bundle size increase < 5KB (zod is small)

---

### Phase 4: Optimistic Updates
**Priority: Medium | Estimated: 4-6 hours**

1. Identify high-frequency mutations:
   - Task status changes (`updateTask` in `ProjectDetail.tsx`)
   - Story sprint assignment (`updateStoryMut` in `AgileBoard.tsx`)
   - Phase status updates (`updatePhaseMut` in `WaterfallView.tsx`)
2. Add `onMutate` + `onError` rollback to each:
   ```ts
   onMutate: async (newData) => {
     await queryClient.cancelQueries({ queryKey })
     const previous = queryClient.getQueryData(queryKey)
     queryClient.setQueryData(queryKey, (old) => optimisticMerge(old, newData))
     return { previous }
   },
   onError: (err, newData, context) => {
     queryClient.setQueryData(queryKey, context.previous)
   }
   ```
3. Create `lib/optimisticHelpers.ts` — shared merge utilities

**Files Expected:**
- `frontend/src/lib/optimisticHelpers.ts`
- `frontend/src/pages/ProjectDetail.tsx` (task mutations)
- `frontend/src/pages/AgileBoard.tsx` (story mutations)
- `frontend/src/pages/WaterfallView.tsx` (phase mutations)

**Verification:**
- [ ] Click task status → UI updates instantly, then syncs with server
- [ ] Network throttled to "Slow 3G" → optimistic UI still responsive
- [ ] Failed mutation → UI rolls back to previous state with toast error

---

### Phase 5: Request Cancellation
**Priority: Low | Estimated: 2-3 hours**

1. Add `AbortController` support to `fetchWithSessionRetry`:
   - Accept optional `signal` in options
   - Forward to `fetch()` calls
2. Wire React Query's automatic cancellation:
   - `queryFn` receives `AbortSignal` from TanStack Query
   - Pass it through to `api.get()` → `fetchWithSessionRetry`
3. Verify on unmount: query is cancelled, no "setState on unmounted component" warnings

**Files Expected:**
- `frontend/src/lib/sessionClient.ts` (AbortController support)
- `frontend/src/lib/api.ts` (signal forwarding)

**Verification:**
- [ ] Navigate away from slow-loading page → network request cancelled
- [ ] No React warnings about state updates on unmounted components
- [ ] Build passes

---

### Phase 6: Normalized Cache Patterns
**Priority: Low | Estimated: 3-4 hours**

1. Create `lib/queryNormalizer.ts` — helper to update entity across multiple query keys:
   ```ts
   export function updateEntityInCache<T extends { id: string }>(
     queryClient: QueryClient,
     entity: T,
     keyPatterns: string[][]
   ) { ... }
   ```
2. Apply to `updateProject` mutation:
   - After successful edit in `Settings.tsx`, also update `['projects', ws.id]` cache
3. Apply to `updateTask` mutation:
   - Update both `['tasks', id]` and `['project', id]` caches

**Files Expected:**
- `frontend/src/lib/queryNormalizer.ts`
- `frontend/src/pages/Settings.tsx` (project update normalization)
- `frontend/src/pages/ProjectDetail.tsx` (task update normalization)

**Verification:**
- [ ] Edit project in Settings → Projects list shows updated name without refetch
- [ ] Update task status → Project progress bar updates without refetch

---

### Phase 7: Service Worker (Offline Support)
**Priority: Low | Estimated: 4-6 hours**

1. Add `vite-plugin-pwa` or custom service worker
2. Cache strategy:
   - App shell (HTML, JS, CSS) → `CacheFirst`
   - API responses → `NetworkFirst` with short TTL
3. Add offline fallback page
4. Add "Update available" toast for new deployments

**Files Expected:**
- `frontend/vite.config.ts` (PWA plugin config)
- `frontend/public/sw.js` (or auto-generated)
- `frontend/src/components/UpdateToast.tsx`

**Verification:**
- [ ] Load app → go offline → reload → app shell still works
- [ ] Deploy new version → existing users see "Update available" toast
- [ ] Build passes, no SW errors in console

---

## Status
Phase 1: Completed ✅ | Phase 2: Completed ✅ | Phase 3: Completed ✅ | Phase 4: Completed ✅ | Phase 5: Completed ✅ | Phase 6: Completed ✅ | Phase 7: Completed ✅

## Notes
- Each phase is independent — can be merged separately
- Phases 1-3 are the highest ROI (safety + performance + data integrity)
- Phases 4-7 are UX refinements and can be deferred
- No backend changes required for any phase

