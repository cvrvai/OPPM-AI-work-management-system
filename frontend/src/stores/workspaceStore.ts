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
          // Always sync currentWorkspace with the fresh API object so that
          // current_user_role (and other fields) are never stale from localStorage.
          const current = get().currentWorkspace
          const freshCurrent = current ? (workspaces.find((w) => w.id === current.id) ?? null) : null
          set({ workspaces, currentWorkspace: freshCurrent ?? workspaces[0] ?? null, loading: false })
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
