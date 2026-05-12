import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listRisksRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmRisksGet,
  createRiskRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmRisksPost,
  updateRiskRouteApiV1WorkspacesWorkspaceIdOppmRisksItemIdPut,
  deleteRiskRouteApiV1WorkspacesWorkspaceIdOppmRisksItemIdDelete,
} from '@/generated/workspace-api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Loader2, Trash2, Save } from 'lucide-react'

interface Risk {
  id: string
  item_number: number
  description: string | null
  rag: string
}

interface RiskEditorProps {
  projectId: string
}

const RAG_OPTIONS = [
  { value: 'green', label: 'Green' },
  { value: 'amber', label: 'Amber' },
  { value: 'red', label: 'Red' },
]

export function RiskEditor({ projectId }: RiskEditorProps) {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)

  const { data: items, isLoading } = useQuery({
    queryKey: ['oppm-risks', projectId, ws?.id],
    queryFn: async () => {
      if (!ws) return []
      const res = await listRisksRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmRisksGet({
        client: workspaceClient,
        path: { workspace_id: ws.id, project_id: projectId },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to load risks')
      }
      return (res.data ?? []) as Risk[]
    },
    enabled: !!ws && !!projectId,
  })

  const [drafts, setDrafts] = useState<Record<number, { description: string; rag: string }>>({})

  const create = useMutation({
    mutationFn: async (itemNumber: number) => {
      if (!ws) throw new Error('No workspace')
      const d = drafts[itemNumber]
      const description = d?.description?.trim()
      if (!description) throw new Error('Description is required')
      const res = await createRiskRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmRisksPost({
        client: workspaceClient,
        path: { workspace_id: ws.id, project_id: projectId },
        body: { item_number: itemNumber, description, rag: d?.rag || 'green' },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to create')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-risks'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
      setDrafts((prev) => {
        const next = { ...prev }
        Object.keys(next).forEach((k) => delete next[Number(k)])
        return next
      })
    },
  })

  const update = useMutation({
    mutationFn: async ({ id, description, rag }: { id: string; description: string; rag: string }) => {
      if (!ws) throw new Error('No workspace')
      const res = await updateRiskRouteApiV1WorkspacesWorkspaceIdOppmRisksItemIdPut({
        client: workspaceClient,
        path: { workspace_id: ws.id, item_id: id },
        body: { description, rag },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to update')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-risks'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
    },
  })

  const remove = useMutation({
    mutationFn: async (itemId: string) => {
      if (!ws) throw new Error('No workspace')
      const res = await deleteRiskRouteApiV1WorkspacesWorkspaceIdOppmRisksItemIdDelete({
        client: workspaceClient,
        path: { workspace_id: ws.id, item_id: itemId },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to delete')
      }
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-risks'] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold'] })
    },
  })

  const byNumber = new Map<number, Risk>()
  for (const item of items ?? []) {
    byNumber.set(item.item_number, item)
  }

  const getDraft = (num: number) => drafts[num] ?? { description: '', rag: 'green' }
  const setDraftField = (num: number, field: 'description' | 'rag', value: string) => {
    setDrafts((prev) => ({ ...prev, [num]: { ...getDraft(num), [field]: value } }))
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-gray-500">Risks (1-4)</div>
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
      ) : (
        <div className="grid grid-cols-1 gap-2">
          {Array.from({ length: 4 }, (_, i) => i + 1).map((num) => {
            const existing = byNumber.get(num)
            const draft = getDraft(num)
            const descValue = existing ? (existing.description ?? '') : draft.description
            const ragValue = existing ? existing.rag : draft.rag
            const hasChanges = existing
              ? (draft.description && draft.description !== (existing.description ?? '')) ||
                (draft.rag && draft.rag !== existing.rag)
              : !!draft.description.trim()

            return (
              <div key={num} className="flex items-center gap-2">
                <span className="w-6 text-xs text-gray-400">{num}</span>
                <input
                  type="text"
                  value={descValue}
                  onChange={(e) => setDraftField(num, 'description', e.target.value)}
                  placeholder={`Risk ${num}`}
                  className="flex-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-900 outline-none focus:border-blue-500"
                />
                <select
                  value={ragValue}
                  onChange={(e) => {
                    const newRag = e.target.value
                    if (existing) {
                      update.mutate({ id: existing.id, description: descValue, rag: newRag })
                    } else {
                      setDraftField(num, 'rag', newRag)
                    }
                  }}
                  className="rounded-md border border-gray-300 bg-white px-1 py-1 text-xs text-gray-900 outline-none focus:border-blue-500"
                >
                  {RAG_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                {existing ? (
                  <>
                    {hasChanges && (
                      <button
                        type="button"
                        onClick={() =>
                          update.mutate({ id: existing.id, description: draft.description, rag: draft.rag || existing.rag })
                        }
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
                    disabled={create.isPending || !draft.description.trim()}
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
