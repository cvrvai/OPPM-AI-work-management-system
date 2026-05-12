import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listSubObjectivesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmSubObjectivesGet,
  createSubObjectiveRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmSubObjectivesPost,
  updateSubObjectiveRouteApiV1WorkspacesWorkspaceIdOppmSubObjectivesSubObjIdPut,
  deleteSubObjectiveRouteApiV1WorkspacesWorkspaceIdOppmSubObjectivesSubObjIdDelete,
} from '@/generated/workspace-api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Loader2, Plus, Trash2, Save } from 'lucide-react'

interface SubObjective {
  id: string
  position: number
  label: string
}

interface SubObjectiveEditorProps {
  projectId: string
}

export function SubObjectiveEditor({ projectId }: SubObjectiveEditorProps) {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)

  const { data: items, isLoading } = useQuery({
    queryKey: ['oppm-sub-objectives', projectId, ws?.id],
    queryFn: async () => {
      if (!ws) return []
      const res = await listSubObjectivesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmSubObjectivesGet({
        client: workspaceClient,
        path: { workspace_id: ws.id, project_id: projectId },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to load sub-objectives')
      }
      return (res.data ?? []) as SubObjective[]
    },
    enabled: !!ws && !!projectId,
  })

  const [drafts, setDrafts] = useState<Record<number, string>>({})

  const create = useMutation({
    mutationFn: async (position: number) => {
      if (!ws) throw new Error('No workspace')
      const label = drafts[position]?.trim()
      if (!label) throw new Error('Label is required')
      const res = await createSubObjectiveRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmSubObjectivesPost({
        client: workspaceClient,
        path: { workspace_id: ws.id, project_id: projectId },
        body: { position, label },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to create')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-sub-objectives'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
      setDrafts((prev) => {
        const next = { ...prev }
        Object.keys(next).forEach((k) => delete next[Number(k)])
        return next
      })
    },
  })

  const update = useMutation({
    mutationFn: async ({ id, label }: { id: string; label: string }) => {
      if (!ws) throw new Error('No workspace')
      const res = await updateSubObjectiveRouteApiV1WorkspacesWorkspaceIdOppmSubObjectivesSubObjIdPut({
        client: workspaceClient,
        path: { workspace_id: ws.id, sub_obj_id: id },
        body: { label },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to update')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-sub-objectives'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
    },
  })

  const remove = useMutation({
    mutationFn: async (subObjId: string) => {
      if (!ws) throw new Error('No workspace')
      const res = await deleteSubObjectiveRouteApiV1WorkspacesWorkspaceIdOppmSubObjectivesSubObjIdDelete({
        client: workspaceClient,
        path: { workspace_id: ws.id, sub_obj_id: subObjId },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to delete')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-sub-objectives'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
    },
  })

  const byPosition = new Map<number, SubObjective>()
  for (const item of items ?? []) {
    byPosition.set(item.position, item)
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-gray-500">Sub-Objectives (1-6)</div>
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
      ) : (
        <div className="grid grid-cols-1 gap-2">
          {Array.from({ length: 6 }, (_, i) => i + 1).map((pos) => {
            const existing = byPosition.get(pos)
            const draft = drafts[pos] ?? ''
            const value = existing ? existing.label : draft
            const hasChanges = existing ? draft && draft !== existing.label : !!draft.trim()

            return (
              <div key={pos} className="flex items-center gap-2">
                <span className="w-6 text-xs text-gray-400">{pos}</span>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, [pos]: e.target.value }))}
                  placeholder={`Sub-objective ${pos}`}
                  className="flex-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-900 outline-none focus:border-blue-500"
                />
                {existing ? (
                  <>
                    {hasChanges && (
                      <button
                        type="button"
                        onClick={() => update.mutate({ id: existing.id, label: draft })}
                        disabled={update.isPending}
                        className="rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {update.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => remove.mutate(existing.id)}
                      disabled={remove.isPending}
                      className="rounded-md border border-red-200 bg-white px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => create.mutate(pos)}
                    disabled={!draft.trim() || create.isPending}
                    className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {create.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
