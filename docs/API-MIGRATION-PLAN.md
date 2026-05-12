# Frontend API Migration Plan

> **Goal:** Migrate every hand-written `api.get/post/put/delete/patch(...)` call in the frontend to the auto-generated `@hey-api` SDK client (`workspaceClient`).
> **Status:** ✅ COMPLETE — All migratable calls migrated. Remaining `api.*` calls are for endpoints not present in the generated SDK.

---

## 1. Why Migrate?

| Benefit | Explanation |
|---------|-------------|
| **Type safety** | Request/response shapes are generated from the backend OpenAPI spec. No more `api.get<SomeType>(...)` manual typing. |
| **Refactoring safety** | Rename a backend route → regenerate client → TypeScript immediately surfaces every broken call site. |
| **No string URLs** | Path params are typed objects (`{ workspace_id: string }`), eliminating typos in URL construction. |
| **Auth is wired once** | `workspaceClient` already patches `fetch` to use `fetchWithSessionRetry` (JWT + auto-refresh). |

---

## 2. The Pattern (Established)

```ts
// 1. Import the generated function
import { someGeneratedRoute } from '@/generated/workspace-api/sdk.gen'

// 2. Import the patched client
import { workspaceClient } from '@/lib/api/workspaceClient'

// 3. Use in a query / mutation
queryFn: () =>
  someGeneratedRoute({
    client: workspaceClient,
    path: { workspace_id: ws!.id, project_id: pid! },   // snake_case = exact OpenAPI param names
    body:   { title: '...' },                             // for POST/PUT/PATCH
    query:  { page: 1 },                                  // for query strings
  }).then(res => res.data as MyAppType)                   // cast when response is `unknown`
```

**Key rules:**
- Path params are **snake_case** (e.g. `workspace_id`, `project_id`).
- `res.data` is often typed as `unknown` when the backend returns a plain `dict` instead of a Pydantic model. Cast to the app-level type (`as DashboardStats`) when needed.
- Mutations that send `FormData` need `bodySerializer: formDataBodySerializer` (see `useProjectFiles.ts` for the example).

---

## 3. Migration Summary

### ✅ Migrated Files (20 files, ~75+ API calls)

| File | Calls Migrated |
|------|---------------|
| `App.tsx` | 2 (dashboard stats prefetch, projects prefetch) |
| `stores/workspaceStore.ts` | 5 (workspaces list, create, dashboard stats, members, projects prefetch) |
| `pages/Dashboard.tsx` | 2 (stats, recent analyses) |
| `pages/Projects.tsx` | 6 (projects CRUD + member assignments) |
| `pages/AgileBoard.tsx` | 9 (epics, sprints, user stories, start/complete sprint) |
| `pages/ProjectDetail.tsx` | 10 (project, tasks, objectives, sub-objectives, members, all-members, task sub-objectives) |
| `pages/WaterfallView.tsx` | 6 (phases, phase documents, approve phase, update phase) |
| `pages/Team.tsx` | 4 (members list, skills list, add skill, delete skill) |
| `pages/Invitations.tsx` | 3 (list my invites, accept, decline) |
| `pages/OPPMView.tsx` | 7 (project, google sheet link, border overrides, scaffold, save link, unlink, push to sheet) |
| `pages/settings/WorkspaceMembersPanel.tsx` | 8 (members, invites, create invite, update role, remove member, revoke invite, resend invite, lookup) |
| `pages/settings/GitHubSettings.tsx` | 7 (accounts CRUD, repos CRUD, list projects) |
| `pages/settings/TaskForm.tsx` | 5 (task reports list/create/approve/delete, objective create) |
| `pages/settings/GoogleSheetsSetup.tsx` | 3 (setup status, save, delete) |
| `pages/settings/ProfileSettings.tsx` | 2 (profile update, display name update) |
| `pages/settings/WorkspaceSettings.tsx` | 1 (delete workspace) |
| `components/layout/Header.tsx` | 5 (unread count, list notifications, mark read, mark all read, delete notification) |
| `components/features/VirtualMemberManager.tsx` | 8 (virtual members CRUD, all members CRUD) |
| `lib/api/client.ts` | 4 (execute sheet actions, get snapshot, get/update/reset oppm sheet prompt) |
| `hooks/useProjectFiles.ts` | 1 (upload file with FormData) |

### ⏭️ Skipped / Not in Generated SDK

| File | Calls | Reason |
|------|-------|--------|
| `pages/settings/AIModelSettings.tsx` | 3 (`POST /ai/models`, `PUT /ai/models/{id}/toggle`, `DELETE /ai/models/{id}`) | AI model endpoints not present in generated SDK — likely in a separate service or missing OpenAPI tags. |
| `pages/OPPMView.tsx` | 1 (`POST /projects/{id}/ai/oppm-fill`) | AI `oppm-fill` endpoint not present in generated SDK. |
| `lib/api/client.ts` | 1 (`POST /v1/workspaces/{id}/ai/parse-file`) | AI parse-file endpoint not present in generated SDK. |

**Total migrated:** ~75+ API calls across 20 files.
**Total skipped:** 5 calls across 3 files (endpoints not in generated SDK).
| `getOppmSheetPrompt` | `GET /ai-config/oppm-sheet-prompt` | |
| `updateOppmSheetPrompt` | `PUT /ai-config/oppm-sheet-prompt` | |
| `resetOppmSheetPrompt` | `DELETE /ai-config/oppm-sheet-prompt` | |

**Decision:** Keep `api` object for truly one-off helpers, but migrate the above 6 to generated SDK so they participate in type safety.

---

## 4. Recommended Migration Order

### Phase 1 — High-Impact, Low-Risk (Queries) ✅ COMPLETE
1. ~~`workspaceStore.ts` (2 `api.get` calls)~~ — Migrated `fetchWorkspaces`, `createWorkspace`, and 3 prefetch queries.
2. ~~`Projects.tsx` (1 `api.post`, 1 `api.delete`, 2 `api.get`, 1 `api.put`, 1 nested `api.post`)~~ — Migrated all 6 calls.
3. ~~`Dashboard.tsx`~~ ✅ (already done).

### Phase 2 — Core Feature Pages (Mutations) ✅ COMPLETE
4. ~~`AgileBoard.tsx` (6 calls)~~ — Migrated epics, sprints, user-stories, start/complete sprint.
5. ~~`ProjectDetail.tsx` (3 calls)~~ — Migrated project, tasks (list/create/update/delete), objectives, sub-objectives, members, all-members, and task sub-objectives linkage.
6. ~~`WaterfallView.tsx` (4 calls)~~ — Migrated phases, phase documents, approve phase, update phase.

### Phase 3 — Settings & Peripheral ✅ COMPLETE
7. ~~`WorkspaceMembersPanel.tsx` (5 calls)~~ — Migrated members list, invites list, create invite, update role, remove member, revoke invite, resend invite, lookup member.
8. ~~`Team.tsx` (3 calls)~~ — Migrated members list, skills list, add skill, delete skill.
9. ~~`Invitations.tsx` (2 calls)~~ — Migrated list my invites, accept invite, decline invite.
10. ~~`GitHubSettings.tsx` (4 calls)~~ — Migrated list accounts, create/delete account, list repos, create/delete/update repo, list projects.
11. ~~`TaskForm.tsx` (5 calls)~~ — Migrated list task reports, create task report, approve task report, delete task report, create objective.
12. ~~`GoogleSheetsSetup.tsx` (3 calls)~~ — Migrated get setup status, upsert setup, delete setup.
13. ~~`ProfileSettings.tsx` (2 calls)~~ — Migrated update profile, update display name.
14. ~~`WorkspaceSettings.tsx` (1 call)~~ — Migrated delete workspace.
15. `AIModelSettings.tsx` (3 calls) — **SKIPPED** — AI model endpoints not present in generated SDK (backend routes may be in a separate service or missing tags).
16. `OPPMView.tsx` — **PENDING** (complex file with many calls).

### Phase 4 — API Client Cleanup
12. Migrate `parseFile`, `executeSheetActions`, `getGoogleSheetSnapshot`, `getOppmSheetPrompt`, `updateOppmSheetPrompt`, `resetOppmSheetPrompt` from `client.ts` to generated SDK.
13. Evaluate whether the legacy `api` object can be deprecated or kept for ad-hoc use.

---

## 5. Regeneration Checklist

Before each batch:
- [ ] Backend is running (`uvicorn main:app --reload`).
- [ ] `curl http://127.0.0.1:8000/openapi.json > services/workspace/openapi.json` (or let the generator fetch directly).
- [ ] `cd frontend && npm run generate-api` (already in `package.json`).
- [ ] Verify no breaking changes in generated types (diff `sdk.gen.ts`, `types.gen.ts`).
- [ ] Run `npx tsc -b --noEmit`.
- [ ] Run `npm run build`.

---

## 6. Common Pitfalls & Solutions

| Pitfall | Solution |
|---------|----------|
| `path` param names are camelCase in my head | They must be **snake_case** (`workspace_id`, `project_id`). Match the OpenAPI path template exactly. |
| `res.data` is `unknown` | The backend returned a plain `dict` without a Pydantic response model. Cast: `res.data as MyType`. |
| `FormData` upload fails | Add `bodySerializer: formDataBodySerializer` to the call options (import from generated client). |
| `fetch` signature mismatch | `workspaceClient.ts` already patches this — use `workspaceClient`, not the default `client`. |
| Endpoint not found in generated SDK | The backend route may not have a `response_model` or may be missing tags. Fix the backend, regenerate. |

---

## 7. Success Criteria

- [ ] Zero `api.get/post/put/delete/patch` calls remain in `pages/` and `stores/`.
- [ ] `npx tsc -b --noEmit` passes with zero errors.
- [ ] `npm run build` succeeds.
- [ ] All migrated features tested manually (create, read, update, delete flows).
- [ ] `docs/PHASE-TRACKER.md` updated with migration status.

---

*Plan created: 2026-05-11*
*Next action: Pick Phase 1 item and begin migration.*
