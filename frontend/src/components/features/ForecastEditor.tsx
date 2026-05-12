import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listForecastsRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmForecastsGet,
  createForecastRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmForecastsPost,
  updateForecastRouteApiV1WorkspacesWorkspaceIdOppmForecastsItemIdPut,
  deleteForecastRouteApiV1WorkspacesWorkspaceIdOppmForecastsItemIdDelete,
} from '@/generated/workspace-api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Loader2, Trash2, Save } from 'lucide-react'

interface Forecast {
  id: string
  item_number: number
  description: string | null
}

interface ForecastEditorProps {
  projectId: string
}

export function ForecastEditor({ projectId }: ForecastEditorProps) {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)

  const { data: items, isLoading } = useQuery({
    queryKey: ['oppm-forecasts', projectId, ws?.id],
    queryFn: async () => {
      if (!ws) return []
      const res = await listForecastsRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmForecastsGet({
        client: workspaceClient,
        path: { workspace_id: ws.id, project_id: projectId },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to load forecasts')
      }
      return (res.data ?? []) as Forecast[]
    },
    enabled: !!ws && !!projectId,
  })

  const [drafts, setDrafts] = useState<Record<number, string>>({})

  const create = useMutation({
    mutationFn: async (itemNumber: number) => {
      if (!ws) throw new Error('No workspace')
      const description = drafts[itemNumber]?.trim()
      if (!description) throw new Error('Description is required')
      const res = await createForecastRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmForecastsPost({
        client: workspaceClient,
        path: { workspace_id: ws.id, project_id: projectId },
        body: { item_number: itemNumber, description },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to create')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-forecasts'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
      setDrafts((prev) => {
        const next = { ...prev }
        Object.keys(next).forEach((k) => delete next[Number(k)])
        return next
      })
    },
  })

  const update = useMutation({
    mutationFn: async ({ id, description }: { id: string; description: string }) => {
      if (!ws) throw new Error('No workspace')
      const res = await updateForecastRouteApiV1WorkspacesWorkspaceIdOppmForecastsItemIdPut({
        client: workspaceClient,
        path: { workspace_id: ws.id, item_id: id },
        body: { description },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to update')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-forecasts'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
    },
  })

  const remove = useMutation({
    mutationFn: async (itemId: string) => {
      if (!ws) throw new Error('No workspace')
      const res = await deleteForecastRouteApiV1WorkspacesWorkspaceIdOppmForecastsItemIdDelete({
        client: workspaceClient,
        path: { workspace_id: ws.id, item_id: itemId },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to delete')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-forecasts'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
    },
  })

  const byNumber = new Map<number, Forecast>()
  for (const item of items ?? []) {
    byNumber.set(item.item_number, item)
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-gray-500">Forecasts (1-4)</div>
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
      ) : (
        <div className="grid grid-cols-1 gap-2">
          {Array.from({ length: 4 }, (_, i) => i + 1).map((num) => {
            const existing = byNumber.get(num)
            const draft = drafts[num] ?? ''
            const value = existing ? (existing.description ?? '') : draft
            const hasChanges = existing ? draft && draft !== (existing.description ?? '') : !!draft.trim()

            return (
              <div key={num} className="flex items-center gap-2">
                <span className="w-6 text-xs text-gray-400">{num}</span>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, [num]: e.target.value }))}
                  placeholder={`Forecast ${num}`}
                  className="flex-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-900 outline-none focus:border-blue-500"
                />
                {existing ? (
                  <>
                    {hasChanges && (
                      <button
                        type="button"
                        onClick={() => update.mutate({ id: existing.id, description: draft })}
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
                      className="rounded-md bg-red-50 px-2 py-1 text-xs text-red-600 hover:bg-red-100 disabled:opacity-50"
                    >
                      {remove.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => create.mutate(num)}
                    disabled={create.isPending || !draft.trim()}
                    className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {create.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Add'}
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
