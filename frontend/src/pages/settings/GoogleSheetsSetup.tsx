import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  getGoogleSheetsSetupStatusRouteApiV1WorkspacesWorkspaceIdGoogleSheetsSetupStatusGet,
  upsertGoogleSheetsSetupRouteApiV1WorkspacesWorkspaceIdGoogleSheetsSetupPut,
  deleteGoogleSheetsSetupRouteApiV1WorkspacesWorkspaceIdGoogleSheetsSetupDelete,
} from '@/generated/workspace-api/sdk.gen'
import type { GoogleSheetsSetupUpsert } from '@/generated/workspace-api/types.gen'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Loader2, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

type SetupStatus = {
  backend_configured: boolean
  service_account_email: string | null
  backend_configuration_error: string | null
  credential_source: string | null
}

export function GoogleSheetsSetup() {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const queryClient = useQueryClient()

  const statusQuery = useQuery({
    queryKey: ['google-sheets-setup-status', ws?.id],
    enabled: !!ws?.id,
    queryFn: () =>
      getGoogleSheetsSetupStatusRouteApiV1WorkspacesWorkspaceIdGoogleSheetsSetupStatusGet({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
      }).then((res) => res.data as SetupStatus),
  })

  const status = statusQuery.data
  const sourceLabel = status?.credential_source === 'env_json'
    ? 'Environment variable JSON'
    : status?.credential_source === 'file'
      ? 'Mounted credential file'
      : status?.credential_source === 'database'
        ? 'Stored in workspace database'
        : 'Not configured'

  const saveMutation = useMutation({
    mutationFn: (payload: { service_account_json: string }) =>
      upsertGoogleSheetsSetupRouteApiV1WorkspacesWorkspaceIdGoogleSheetsSetupPut({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
        body: payload as GoogleSheetsSetupUpsert,
      }).then((res) => res.data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['google-sheets-setup-status', ws?.id] })
      setFeedback({ type: 'success', message: 'Google Sheets credential saved to workspace.' })
    },
    onError: (error: Error) => {
      setFeedback({ type: 'error', message: error.message || 'Failed to save workspace credential.' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      deleteGoogleSheetsSetupRouteApiV1WorkspacesWorkspaceIdGoogleSheetsSetupDelete({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
      }).then((res) => res.data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['google-sheets-setup-status', ws?.id] })
      setFeedback({ type: 'success', message: 'Stored workspace credential removed.' })
    },
    onError: (error: Error) => {
      setFeedback({ type: 'error', message: error.message || 'Failed to remove workspace credential.' })
    },
  })

  const [jsonText, setJsonText] = useState('')
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const handleSaveCredential = () => {
    const trimmed = jsonText.trim()
    if (!trimmed) {
      setFeedback({ type: 'error', message: 'Paste a service account JSON before saving.' })
      return
    }
    try {
      JSON.parse(trimmed)
    } catch {
      setFeedback({ type: 'error', message: 'Invalid JSON format. Please paste a valid service account JSON key.' })
      return
    }
    setFeedback(null)
    saveMutation.mutate({ service_account_json: trimmed })
  }

  const handleRemoveCredential = () => {
    setFeedback(null)
    deleteMutation.mutate()
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-text">Google Sheets Write Setup</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Live Browser Preview is read-only. AI can edit your linked sheet only after backend Google credentials are configured.
            </p>
          </div>
          <span className={cn(
            'rounded-full px-2.5 py-1 text-xs font-semibold',
            status?.backend_configured
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-amber-100 text-amber-800'
          )}>
            {status?.backend_configured ? 'Write enabled' : 'Write disabled'}
          </span>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface-alt/70 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Credential source</p>
            <p className="mt-1 text-sm text-text">{sourceLabel}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-alt/70 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">Service account email</p>
            <p className="mt-1 break-all text-sm text-text">{status?.service_account_email || 'Not available yet'}</p>
          </div>
        </div>

        {status?.backend_configuration_error ? (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {status.backend_configuration_error}
          </div>
        ) : null}

        <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm text-text-secondary">
          <li>Enable Google Sheets API and Google Drive API in your Google Cloud project.</li>
          <li>Create a service account and download its JSON key.</li>
          <li>Either place it at <span className="font-medium text-text">services/secrets/google-service-account.json</span> on the server, or store it in the workspace database below.</li>
          <li>Share each target Google Sheet with the service account email as Editor.</li>
          <li>Restart Docker services so the core container picks up the mounted credential file.</li>
        </ol>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <p className="text-sm text-text-secondary mb-2">Save service account JSON into workspace storage (admins only).</p>
            <textarea
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              placeholder='Paste service account JSON here'
              className="w-full h-40 rounded-md border border-border p-3 text-sm font-mono"
            />
            {feedback ? (
              <div
                className={cn(
                  'mt-3 rounded-lg border px-3 py-2 text-sm',
                  feedback.type === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-red-200 bg-red-50 text-red-700'
                )}
              >
                {feedback.message}
              </div>
            ) : null}
            <div className="mt-3 flex gap-2">
              <button
                onClick={handleSaveCredential}
                disabled={!ws?.id || !jsonText.trim() || saveMutation.isPending}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saveMutation.isPending ? 'Saving...' : 'Save to Workspace'}
              </button>
              <button
                onClick={handleRemoveCredential}
                disabled={!ws?.id || deleteMutation.isPending || !status?.credential_source}
                className="rounded-lg border border-border px-4 py-2 text-sm"
              >
                {deleteMutation.isPending ? 'Removing...' : 'Remove Stored Credential'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
