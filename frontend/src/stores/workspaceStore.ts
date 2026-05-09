import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/lib/api'
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
        const wsPath = `/v1/workspaces/${ws.id}`
        // Fire-and-forget prefetch calls — we don't await them
        queryClient.prefetchQuery({
          queryKey: ['projects', ws.id],
          queryFn: async () => {
            const res = await api.get<{ items: unknown[]; total: number }>(`${wsPath}/projects`)
            return res.items ?? []
          },
          staleTime: 30_000,
        })
        queryClient.prefetchQuery({
          queryKey: ['dashboard-stats', ws.id],
          queryFn: () => api.get(`${wsPath}/dashboard/stats`),
          staleTime: 30_000,
        })
        queryClient.prefetchQuery({
          queryKey: ['members', ws.id],
          queryFn: () => api.get(`${wsPath}/members`),
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
          const workspaces = await api.get<Workspace[]>('/v1/workspaces')
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
        const ws = await api.post<Workspace>('/v1/workspaces', { name, slug, description })
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
