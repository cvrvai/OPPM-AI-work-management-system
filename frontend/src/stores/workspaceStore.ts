import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listWorkspacesApiV1WorkspacesGet,
  createWorkspaceRouteApiV1WorkspacesPost,
  listProjectsRouteApiV1WorkspacesWorkspaceIdProjectsGet,
  dashboardStatsApiV1WorkspacesWorkspaceIdDashboardStatsGet,
  listMembersApiV1WorkspacesWorkspaceIdMembersGet,
} from '@/generated/workspace-api/sdk.gen'
import { queryClient } from '@/lib/api/queryClient'
import type { Workspace } from '@/types'

interface WorkspaceState {
  workspaces: Workspace[]
  currentWorkspace: Workspace | null
  loading: boolean
  setCurrentWorkspace: (ws: Workspace) => void
  fetchWorkspaces: () => Promise<void>
  createWorkspace: (name: string, slug: string, description?: string) => Promise<Workspace>
}

let lastFetchAt = 0
const FETCH_DEBOUNCE_MS = 5_000

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      workspaces: [],
      currentWorkspace: null,
      loading: false,

      setCurrentWorkspace: (ws) => {
        set({ currentWorkspace: ws })
        // Warm the React Query cache for the new workspace so the first page
        // load feels instant instead of showing skeletons for 1–2 s.
        // Fire-and-forget prefetch calls — we don't await them
        queryClient.prefetchQuery({
          queryKey: ['projects', ws.id],
          queryFn: async () => {
            const res = await listProjectsRouteApiV1WorkspacesWorkspaceIdProjectsGet({
              client: workspaceClient,
              path: { workspace_id: ws.id },
            })
            const data = res.data as { items: unknown[]; total: number }
            return data.items ?? []
          },
          staleTime: 30_000,
        })
        queryClient.prefetchQuery({
          queryKey: ['dashboard-stats', ws.id],
          queryFn: () =>
            dashboardStatsApiV1WorkspacesWorkspaceIdDashboardStatsGet({
              client: workspaceClient,
              path: { workspace_id: ws.id },
            }).then((res) => res.data),
          staleTime: 30_000,
        })
        queryClient.prefetchQuery({
          queryKey: ['members', ws.id],
          queryFn: () =>
            listMembersApiV1WorkspacesWorkspaceIdMembersGet({
              client: workspaceClient,
              path: { workspace_id: ws.id },
            }).then((res) => res.data),
          staleTime: 5 * 60 * 1000,
        })
      },

      fetchWorkspaces: async () => {
        // Short-term memory cache: skip re-fetching within 5s of last success.
        const now = Date.now()
        if (now - lastFetchAt < FETCH_DEBOUNCE_MS && get().workspaces.length > 0) {
          return
        }
        set({ loading: true })
        try {
          const res = await listWorkspacesApiV1WorkspacesGet({ client: workspaceClient })
          const workspaces = (res.data ?? []) as Workspace[]
          // Always sync currentWorkspace with the fresh API object so that
          // current_user_role (and other fields) are never stale from localStorage.
          const current = get().currentWorkspace
          const freshCurrent = current ? (workspaces.find((w) => w.id === current.id) ?? null) : null
          set({ workspaces, currentWorkspace: freshCurrent ?? workspaces[0] ?? null, loading: false })
          lastFetchAt = Date.now()
        } catch {
          set({ loading: false })
        }
      },

      createWorkspace: async (name, slug, description = '') => {
        const res = await createWorkspaceRouteApiV1WorkspacesPost({
          client: workspaceClient,
          body: { name, slug, description },
        })
        const ws = res.data as Workspace
        const workspaces = [...get().workspaces, ws]
        set({ workspaces, currentWorkspace: ws })
        lastFetchAt = Date.now()
        return ws
      },
    }),
    {
      name: 'oppm-workspace',
      partialize: (state) => ({ currentWorkspace: state.currentWorkspace }),
    }
  )
)
