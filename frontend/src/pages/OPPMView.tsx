/**
 * OPPMView — minimal scaffold workspace.
 *
 * This phase intentionally removes the current OPPM feature flows
 * (saved template loading, AI fill, download/export, guide/tool controls)
 * to focus on rebuilding layout structure step-by-step.
 */

import React, { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { transformExcelToFortune } from '@corbe30/fortune-excel'
import { ArrowLeft, ExternalLink, Link2, Loader2, Send, Unplug } from 'lucide-react'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'

interface GoogleSheetLinkState {
  connected: boolean
  spreadsheet_id: string | null
  spreadsheet_url: string | null
  backend_configured: boolean
  service_account_email: string | null
  backend_configuration_error?: string | null
}

interface GoogleSheetPushResult {
  spreadsheet_id: string
  spreadsheet_url: string
  updated_sheets: string[]
  rows_written: {
    summary: number
    tasks: number
    members: number
  }
}

function extractSpreadsheetId(value: string | null | undefined): string | null {
  if (!value) return null
  const trimmed = value.trim()
  const match = trimmed.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/)
  if (match?.[1]) return match[1]
  if (/^[a-zA-Z0-9-_]{20,}$/.test(trimmed)) return trimmed
  return null
}

function getGoogleSheetEmbedUrl(spreadsheetId: string | null): string | null {
  if (!spreadsheetId) return null
  return `https://docs.google.com/spreadsheets/d/${spreadsheetId}/preview?rm=minimal&single=true&widget=true&headers=false`
}

// ══════════════════════════════════════════════════════════════
// OPPMView
// ══════════════════════════════════════════════════════════════
export function OPPMView() {
  const { id } = useParams<{ id: string }>()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const queryClient = useQueryClient()

  // Keep workspace-switch guard active while the page is simplified.
  useWorkspaceNavGuard()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [sheetData, setSheetData] = useState<any[]>([])
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetRef = useRef<any>(null)
  const [sheetKey, setSheetKey] = useState(0)
  const [sheetInput, setSheetInput] = useState('')
  const [actionNotice, setActionNotice] = useState<string | null>(null)
  const [sheetLoadState, setSheetLoadState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [sheetLoadError, setSheetLoadError] = useState<string | null>(null)
  const [sheetRefreshToken, setSheetRefreshToken] = useState(0)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  const googleSheetQuery = useQuery({
    queryKey: ['oppm-google-sheet', id, ws?.id],
    queryFn: () => api.get<GoogleSheetLinkState>(`${wsPath}/projects/${id}/oppm/google-sheet`),
    enabled: !!ws && !!id,
  })

  useEffect(() => {
    const linkedValue = googleSheetQuery.data?.spreadsheet_url ?? googleSheetQuery.data?.spreadsheet_id ?? ''
    setSheetInput(linkedValue)
  }, [googleSheetQuery.data?.spreadsheet_id, googleSheetQuery.data?.spreadsheet_url])

  const saveGoogleSheetLink = useMutation({
    mutationFn: async () => {
      const value = sheetInput.trim()
      if (!value) {
        throw new Error('Enter a Google Sheet URL or spreadsheet ID first.')
      }
      return api.put<GoogleSheetLinkState>(`${wsPath}/projects/${id}/oppm/google-sheet`, {
        spreadsheet_url: value,
      })
    },
    onSuccess: (data) => {
      setActionNotice(`Linked Google Sheet ${data.spreadsheet_id}.`)
      setSheetRefreshToken((value) => value + 1)
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const unlinkGoogleSheet = useMutation({
    mutationFn: () => api.delete(`${wsPath}/projects/${id}/oppm/google-sheet`),
    onSuccess: () => {
      setActionNotice('Removed the Google Sheet link for this project.')
      setSheetInput('')
      setSheetData([])
      setSheetLoadState('idle')
      setSheetLoadError(null)
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const pushToGoogleSheet = useMutation({
    mutationFn: async () => {
      const fill = await api.post(`${wsPath}/projects/${id}/ai/oppm-fill`, {})
      return api.post<GoogleSheetPushResult>(`${wsPath}/projects/${id}/oppm/google-sheet/push`, fill)
    },
    onSuccess: (data) => {
      setActionNotice(
        `Pushed AI-filled data to Google Sheets. Summary: ${data.rows_written.summary}, tasks: ${data.rows_written.tasks}, members: ${data.rows_written.members}.`
      )
      setSheetRefreshToken((value) => value + 1)
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const googleSheet = googleSheetQuery.data
  const linkedSheetUrl = googleSheet?.spreadsheet_url ?? ''
  const linkedSpreadsheetId = googleSheet?.spreadsheet_id ?? extractSpreadsheetId(sheetInput)
  const embedPreviewUrl = getGoogleSheetEmbedUrl(linkedSpreadsheetId)
  const buttonsDisabled = !ws || !id
  const hasLinkedSheet = !!googleSheet?.connected

  useEffect(() => {
    if (!ws || !id || !googleSheet?.connected) {
      setSheetData([])
      setSheetLoadState('idle')
      setSheetLoadError(null)
      return
    }

    if (!googleSheet.backend_configured) {
      setSheetData([])
      setSheetLoadState('error')
      setSheetLoadError(googleSheet.backend_configuration_error || 'Google integration is not configured on the backend.')
      return
    }

    let cancelled = false
    setSheetLoadState('loading')
    setSheetLoadError(null)

    const loadLinkedSheet = async () => {
      try {
        const blob = await api.getBlob(`${wsPath}/projects/${id}/oppm/google-sheet/xlsx`)
        if (cancelled) return
        const file = new File([blob], `linked-google-sheet-${id}.xlsx`, {
          type: blob.type || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        await transformExcelToFortune(file, setSheetData, setSheetKey, sheetRef)
        if (!cancelled) {
          setSheetLoadState('ready')
        }
      } catch (error) {
        if (cancelled) return
        setSheetData([])
        setSheetLoadState('error')
        setSheetLoadError(error instanceof Error ? error.message : 'Failed to load the linked Google Sheet.')
      }
    }

    loadLinkedSheet()

    return () => {
      cancelled = true
    }
  }, [
    googleSheet?.backend_configuration_error,
    googleSheet?.backend_configured,
    googleSheet?.connected,
    googleSheet?.spreadsheet_id,
    id,
    ws,
    wsPath,
    sheetRefreshToken,
  ])

  return (
    <div className="font-['Inter',system-ui,sans-serif]">
      <div className="sticky top-0 z-30 bg-white border-b border-gray-200 shadow-sm -mx-4 sm:-mx-6 px-4 sm:px-6">
        <div className="flex items-center gap-2 py-2">
          <Link
            to={`/projects/${id}`}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-bold uppercase tracking-widest text-gray-400">
              One Page Project Manager
            </p>
            <h1 className="text-sm font-bold text-gray-900 truncate">
              {hasLinkedSheet ? 'Linked Google Sheet' : 'Link Google Sheet'}
            </h1>
          </div>
        </div>

        <div className="pb-3">
          <div className="rounded-xl border border-blue-100 bg-blue-50/70 px-3 py-3">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
              <div className="min-w-0 flex-1">
                <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-blue-700">
                  Google Sheet URL or Spreadsheet ID
                </label>
                <input
                  value={sheetInput}
                  onChange={(e) => setSheetInput(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/... or spreadsheet ID"
                  className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500"
                />
                <p className="mt-1.5 text-xs text-blue-800/80">
                  {googleSheet?.service_account_email
                    ? `Share the target spreadsheet with ${googleSheet.service_account_email} before pushing.`
                    : googleSheet?.backend_configuration_error
                      ? `${googleSheet.backend_configuration_error}. Save and browser preview can still work without backend Google credentials.`
                    : 'The backend must be configured with a Google service account before push is available.'}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => saveGoogleSheetLink.mutate()}
                  disabled={buttonsDisabled || saveGoogleSheetLink.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saveGoogleSheetLink.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                  Save Link
                </button>

                <button
                  type="button"
                  onClick={() => pushToGoogleSheet.mutate()}
                  disabled={buttonsDisabled || !googleSheet?.connected || !googleSheet.backend_configured || pushToGoogleSheet.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pushToGoogleSheet.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Push AI Fill
                </button>

                <button
                  type="button"
                  onClick={() => linkedSheetUrl && window.open(linkedSheetUrl, '_blank', 'noopener,noreferrer')}
                  disabled={!linkedSheetUrl}
                  className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open Sheet
                </button>

                <button
                  type="button"
                  onClick={() => unlinkGoogleSheet.mutate()}
                  disabled={buttonsDisabled || !googleSheet?.connected || unlinkGoogleSheet.isPending}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {unlinkGoogleSheet.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />}
                  Unlink
                </button>
              </div>
            </div>

            <div className="mt-3 flex flex-col gap-1 text-xs text-gray-600 sm:flex-row sm:items-center sm:justify-between">
              <span>
                {googleSheetQuery.isLoading
                  ? 'Loading linked Google Sheet state...'
                  : googleSheet?.connected
                    ? `Linked spreadsheet: ${googleSheet.spreadsheet_id}`
                    : 'No Google Sheet linked yet.'}
              </span>
              <span className={googleSheet?.backend_configured ? 'text-emerald-700' : 'text-amber-700'}>
                {googleSheet?.backend_configured ? 'Backend Google integration ready' : 'Backend Google integration not configured'}
              </span>
            </div>

            {actionNotice ? (
              <p className="mt-2 rounded-lg border border-blue-100 bg-white px-3 py-2 text-sm text-gray-700">
                {actionNotice}
              </p>
            ) : null}

            {!actionNotice && googleSheet?.backend_configuration_error ? (
              <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                {googleSheet.backend_configuration_error}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3">
        {!hasLinkedSheet ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
            <h2 className="text-lg font-semibold text-gray-900">No linked Google Sheet yet</h2>
            <p className="mx-auto mt-2 max-w-2xl text-sm text-gray-600">
              Save a Google Sheet URL or spreadsheet ID above to load that existing form inside the OPPM page.
              The hardcoded scaffold is no longer the primary display path.
            </p>
          </div>
        ) : sheetLoadState === 'loading' ? (
          <div className="flex items-center justify-center py-24 gap-3 rounded-xl border border-gray-200 bg-white">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-sm text-gray-500">Loading linked Google Sheet…</span>
          </div>
        ) : sheetLoadState === 'error' ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-8 text-center">
              <h2 className="text-lg font-semibold text-red-700">Could not load the linked sheet through the backend</h2>
              <p className="mt-2 text-sm text-red-600">
                {sheetLoadError || 'The linked Google Sheet could not be loaded into the app.'}
              </p>
              <p className="mt-2 text-sm text-red-700/90">
                Switching to browser preview mode is the fastest workaround while the Docker backend is rebuilt and configured.
              </p>
              <div className="mt-4 flex justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setSheetRefreshToken((value) => value + 1)}
                  className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
                >
                  Retry Backend Render
                </button>
                <button
                  type="button"
                  onClick={() => linkedSheetUrl && window.open(linkedSheetUrl, '_blank', 'noopener,noreferrer')}
                  disabled={!linkedSheetUrl}
                  className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50"
                >
                  Open in Google Sheets
                </button>
              </div>
            </div>

            {embedPreviewUrl ? (
              <div className="overflow-hidden rounded-xl border border-amber-200 bg-white shadow-sm">
                <div className="border-b border-amber-100 bg-amber-50 px-4 py-3">
                  <p className="text-sm font-semibold text-amber-800">Browser Preview Fallback</p>
                  <p className="mt-1 text-xs text-amber-700">
                    This preview uses your browser session instead of backend XLSX export. It is read-only and may look slightly different from the full FortuneSheet render.
                  </p>
                </div>
                <iframe
                  title="Linked Google Sheet Preview"
                  src={embedPreviewUrl}
                  className="h-[70vh] min-h-[520px] w-full border-0 bg-white"
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
              </div>
            ) : null}
          </div>
        ) : sheetData.length > 0 ? (
          <div
            className="bg-white border border-gray-300 rounded-lg overflow-hidden"
            style={{ height: 'calc(100vh - 116px)', minHeight: 500 }}
          >
            <Workbook
              key={sheetKey}
              ref={sheetRef}
              data={sheetData}
              allowEdit={false}
              showToolbar={false}
              onChange={() => {}}
              onOp={() => {}}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center py-24 gap-3 rounded-xl border border-gray-200 bg-white">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-sm text-gray-500">Preparing the linked Google Sheet…</span>
          </div>
        )}
      </div>
    </div>
  )
}
