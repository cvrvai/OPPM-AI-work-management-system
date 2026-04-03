import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/lib/api'
import type { Workspace } from '@/types'

interface WorkspaceState {
  workspaces: Workspace[]
  currentWorkspace: Workspace | null
  loading: boolean
  setCurrentWorkspace: (ws: Workspace) => void
  fetchWorkspaces: () => Promise<void>
  createWorkspace: (name: string, slug: string, description?: string) => Promise<Workspace>
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      workspaces: [],
      currentWorkspace: null,
      loading: false,

      setCurrentWorkspace: (ws) => set({ currentWorkspace: ws }),

      fetchWorkspaces: async () => {
        set({ loading: true })
        try {
          const workspaces = await api.get<Workspace[]>('/v1/workspaces')
          set({ workspaces, loading: false })
          // Validate that the persisted workspace belongs to this user.
          // If not (stale data from a previous session/user), switch to first available.
          const current = get().currentWorkspace
          if (!current || !workspaces.find((w) => w.id === current.id)) {
            set({ currentWorkspace: workspaces[0] ?? null })
          }
        } catch {
          set({ loading: false })
        }
      },

      createWorkspace: async (name, slug, description = '') => {
        const ws = await api.post<Workspace>('/v1/workspaces', { name, slug, description })
        const workspaces = [...get().workspaces, ws]
        set({ workspaces, currentWorkspace: ws })
        return ws
      },
    }),
    {
      name: 'oppm-workspace',
      partialize: (state) => ({ currentWorkspace: state.currentWorkspace }),
    }
  )
)
