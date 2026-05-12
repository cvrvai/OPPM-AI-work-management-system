import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { workspaceClient } from '@/lib/api/workspaceClient'
import { deleteWorkspaceRouteApiV1WorkspacesWorkspaceIdDelete } from '@/generated/workspace-api/sdk.gen'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { AlertTriangle, Loader2 } from 'lucide-react'

export function WorkspaceSettings() {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces)
  const navigate = useNavigate()
  const currentRole = ws?.current_user_role ?? ws?.role ?? 'viewer'
  const isOwner = currentRole === 'owner'
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteName, setDeleteName] = useState('')
  const [deleteError, setDeleteError] = useState('')

  const resetDeleteState = () => {
    setShowDeleteConfirm(false)
    setDeleteName('')
    setDeleteError('')
  }

  const deleteWorkspaceMutation = useMutation({
    mutationFn: () =>
      deleteWorkspaceRouteApiV1WorkspacesWorkspaceIdDelete({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
      }).then((res) => res.data),
    onSuccess: async () => {
      resetDeleteState()
      await fetchWorkspaces()
      navigate('/')
    },
    onError: (error: Error) => {
      setDeleteError(error.message)
    },
  })

  if (!ws) {
    return null
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-white p-6 shadow-sm">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-text">Workspace Overview</h2>
            <p className="mt-1 text-sm text-text-secondary">
              Review the current workspace identity and the role you hold inside it.
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-600">
            {currentRole}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-border bg-surface-alt/70 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Workspace name</p>
            <p className="mt-2 text-sm font-semibold text-text">{ws.name}</p>
          </div>
          <div className="rounded-xl border border-border bg-surface-alt/70 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Slug</p>
            <p className="mt-2 text-sm font-semibold text-text">{ws.slug}</p>
          </div>
          <div className="rounded-xl border border-border bg-surface-alt/70 p-4 md:col-span-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Description</p>
            <p className="mt-2 text-sm text-text-secondary">
              {ws.description || 'No workspace description has been added yet.'}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-surface-alt/70 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Created</p>
            <p className="mt-2 text-sm text-text-secondary">{new Date(ws.created_at).toLocaleDateString()}</p>
          </div>
          <div className="rounded-xl border border-border bg-surface-alt/70 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Last updated</p>
            <p className="mt-2 text-sm text-text-secondary">{new Date(ws.updated_at).toLocaleDateString()}</p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-danger/25 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-start gap-3">
          <div className="rounded-full bg-danger/10 p-2 text-danger">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-text">Danger Zone</h2>
            <p className="mt-1 text-sm text-text-secondary">
              Deleting a workspace removes its projects, tasks, invites, and related planning data permanently.
            </p>
          </div>
        </div>

        {!isOwner ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Only the workspace owner can delete this workspace. Your current role is <strong className="capitalize">{currentRole}</strong>.
          </div>
        ) : showDeleteConfirm ? (
          <div className="space-y-4 rounded-2xl border border-danger/25 bg-danger/5 p-4">
            <div className="space-y-1">
              <p className="text-sm font-semibold text-text">Confirm workspace deletion</p>
              <p className="text-sm text-text-secondary">
                Type <strong>{ws.name}</strong> to confirm. This cannot be undone.
              </p>
            </div>

            <input
              value={deleteName}
              onChange={(e) => setDeleteName(e.target.value)}
              placeholder={ws.name}
              className="w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors focus:border-danger focus:ring-4 focus:ring-danger/10"
            />

            {deleteError && (
              <p className="text-sm text-danger">{deleteError}</p>
            )}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={resetDeleteState}
                className="rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-alt"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteWorkspaceMutation.mutate()}
                disabled={deleteWorkspaceMutation.isPending || deleteName.trim() !== ws.name}
                className="inline-flex items-center justify-center rounded-xl bg-danger px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {deleteWorkspaceMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Delete Workspace'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface-alt/70 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-text">Delete {ws.name}</p>
              <p className="text-sm text-text-secondary">Make sure you really want to remove the entire workspace before continuing.</p>
            </div>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center justify-center rounded-xl bg-danger px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-700"
            >
              Delete Workspace
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
