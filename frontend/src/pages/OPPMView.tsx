/**
 * OPPMView — Full-viewport OPPM editor with backend-generated scaffold.
 *
 * UX goals:
 *  - The form fills the entire viewport so the user sees the full OPPM at once
 *  - Minimal chrome: back button, project title, mode toggle, one action button
 *  - Control panel is a slide-down, not a permanent fixture
 *  - No "Preparing editor…" delay — backend returns ready-to-render JSON
 */

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Link2,
  Loader2,
  Send,
  Unplug,
} from 'lucide-react'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { useChatContext } from '@/hooks/useChatContext'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatStore } from '@/stores/chatStore'

/* ── Types ── */

interface GoogleSheetLinkState {
  connected: boolean
  spreadsheet_id: string | null
  spreadsheet_url: string | null
  oppm_sheet_gid: number | null
  backend_configured: boolean
  service_account_email: string | null
  backend_configuration_error?: string | null
}

interface GoogleSheetPushResult {
  spreadsheet_id: string
  spreadsheet_url: string
  updated_sheets: string[]
  rows_written: {
    oppm?: number
    summary: number
    tasks: number
    members: number
  }
  diagnostics?: {
    mapping?: {
      source?: string
      resolved_fields?: Record<string, { source?: string; target?: string }>
      task_anchor?: { column?: string; first_row?: number }
    }
    writes?: { skipped?: number }
  }
}

interface OppmScaffoldResponse {
  sheet_data: any[]
  source: string
}

interface BorderOverride {
  cell_row: number
  cell_col: number
  side: string
  style: string
  color: string
}

/* ── Helpers ── */

function extractSpreadsheetId(value: string | null | undefined): string | null {
  if (!value) return null
  const trimmed = value.trim()
  const match = trimmed.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/)
  if (match?.[1]) return match[1]
  if (/^[a-zA-Z0-9-_]{20,}$/.test(trimmed)) return trimmed
  return null
}

function getGoogleSheetEmbedUrl(spreadsheetId: string | null, gid?: number | null): string | null {
  if (!spreadsheetId) return null
  const base = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit?rm=minimal&widget=true&headers=false`
  return gid != null ? `${base}#gid=${gid}` : base
}

const BORDER_STYLE_MAP: Record<string, number> = {
  thin: 1, hair: 2, dotted: 3, dashed: 4, medium_dash_dot: 5,
  medium: 8, double: 7, thick: 9, medium_dashed: 10, slant_dash_dot: 11, none: 0,
}

const SIDE_KEYS: Record<string, string> = { top: 't', bottom: 'b', left: 'l', right: 'r' }

function mergeBorderOverrides(sheet: any[], overrides: BorderOverride[]): any[] {
  if (!sheet?.length || !overrides?.length) return sheet
  return sheet.map((s) => {
    if (!s.config) return s
    const existing: any[] = s.config.borderInfo || []
    const existingMap = new Map<string, any>()
    for (const bi of existing) {
      if (bi.rangeType === 'cell' && bi.value) {
        for (const side of ['l', 'r', 't', 'b']) {
          if (bi.value[side]) {
            existingMap.set(`${bi.value.row_index}_${bi.value.col_index}_${side}`, bi)
          }
        }
      }
    }
    for (const o of overrides) {
      const sideKey = SIDE_KEYS[o.side]
      if (!sideKey) continue
      const styleNum = BORDER_STYLE_MAP[o.style] ?? 1
      const mapKey = `${o.cell_row}_${o.cell_col}_${sideKey}`
      const existingBi = existingMap.get(mapKey)
      if (existingBi) {
        existingBi.value[sideKey] = { style: styleNum, color: o.color }
      } else {
        const newBi = {
          rangeType: 'cell',
          value: { row_index: o.cell_row, col_index: o.cell_col, [sideKey]: { style: styleNum, color: o.color } },
        }
        existing.push(newBi)
        existingMap.set(mapKey, newBi)
      }
    }
    return { ...s, config: { ...s.config, borderInfo: existing } }
  })
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

  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const projectQuery = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn: () => api.get<{ title: string }>(`${wsPath}/projects/${id}`),
    enabled: !!ws && !!id,
  })

  useChatContext('project', id, projectQuery.data?.title)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [sheetData, setSheetData] = useState<any[]>([])
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetRef = useRef<any>(null)
  const [sheetKey, setSheetKey] = useState(0)
  const [sheetInput, setSheetInput] = useState('')
  const [actionNotice, setActionNotice] = useState<string | null>(null)
  const [sheetLoadState, setSheetLoadState] = useState<'idle' | 'loading' | 'preview' | 'error'>('idle')
  const [sheetLoadError, setSheetLoadError] = useState<string | null>(null)
  const [sheetRefreshToken, setSheetRefreshToken] = useState(0)
  const [editorMode, setEditorMode] = useState<'app' | 'google'>('app')
  const [showControlPanel, setShowControlPanel] = useState(false)

  const googleSheetQuery = useQuery({
    queryKey: ['oppm-google-sheet', id, ws?.id],
    queryFn: () => api.get<GoogleSheetLinkState>(`${wsPath}/projects/${id}/oppm/google-sheet`),
    enabled: !!ws && !!id,
  })

  // Fetch AI/user border overrides for the FortuneSheet
  const borderOverridesQuery = useQuery({
    queryKey: ['oppm-border-overrides', id, ws?.id],
    queryFn: () => api.get<{ items: BorderOverride[] }>(`${wsPath}/projects/${id}/oppm/border-overrides`),
    enabled: !!ws && !!id,
  })

  // Fetch FortuneSheet scaffold from backend (exact Google Sheet layout)
  const scaffoldQuery = useQuery({
    queryKey: ['oppm-scaffold', id, ws?.id],
    queryFn: () => api.get<OppmScaffoldResponse>(`${wsPath}/projects/${id}/oppm/scaffold`),
    enabled: !!ws && !!id,
    staleTime: Infinity,
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
      const fill = await api.post<Record<string, unknown>>(`${wsPath}/projects/${id}/ai/oppm-fill`, {})
      return api.post<GoogleSheetPushResult>(`${wsPath}/projects/${id}/oppm/google-sheet/push`, fill)
    },
    onSuccess: (data) => {
      const oppmWriteInfo = typeof data.rows_written.oppm === 'number' && data.rows_written.oppm > 0
        ? ` OPPM task rows: ${data.rows_written.oppm}.`
        : ''
      const mappingSource = data.diagnostics?.mapping?.source
      const resolvedFieldCount = data.diagnostics?.mapping?.resolved_fields
        ? Object.keys(data.diagnostics.mapping.resolved_fields).length
        : 0
      const mappingInfo = mappingSource
        ? mappingSource === 'helper_sheet_profile'
          ? ` Auto-targeted helper sheets${resolvedFieldCount ? ` (${resolvedFieldCount} field${resolvedFieldCount === 1 ? '' : 's'})` : ''}.`
          : ` Auto-target: ${mappingSource}${resolvedFieldCount ? ` (${resolvedFieldCount} field${resolvedFieldCount === 1 ? '' : 's'})` : ''}.`
        : ''
      setActionNotice(
        `Pushed AI-filled data to Google Sheets.${oppmWriteInfo}${mappingInfo} Summary: ${data.rows_written.summary}, tasks: ${data.rows_written.tasks}, members: ${data.rows_written.members}.`
      )
      setSheetRefreshToken((value) => value + 1)
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const handleSetEditorMode = (mode: 'app' | 'google') => {
    setEditorMode(mode)
    if (mode === 'app' && sheetData.length === 0 && scaffoldQuery.data?.sheet_data) {
      setSheetData(scaffoldQuery.data.sheet_data)
      setSheetKey((k) => k + 1)
    }
  }

  const googleSheet = googleSheetQuery.data
  const hasLinkedSheet = !!googleSheet?.connected
  const linkedSheetUrl = googleSheet?.spreadsheet_url ?? ''
  const linkedSpreadsheetId = googleSheet?.spreadsheet_id ?? extractSpreadsheetId(sheetInput)
  const embedPreviewUrl = getGoogleSheetEmbedUrl(linkedSpreadsheetId, googleSheet?.oppm_sheet_gid)
  const previewSrc = embedPreviewUrl ? `${embedPreviewUrl}${embedPreviewUrl.includes('?') ? '&' : '?'}refresh=${sheetRefreshToken}` : null
  const buttonsDisabled = !ws || !id

  const patchedSheetData = useMemo(() => {
    const overrides = borderOverridesQuery.data?.items ?? []
    return mergeBorderOverrides(sheetData, overrides)
  }, [sheetData, borderOverridesQuery.data])

  const setOppmSheet = useChatStore((s) => s.setOppmSheet)
  useEffect(() => {
    if (googleSheet?.connected && googleSheet.spreadsheet_id) {
      setOppmSheet(googleSheet.spreadsheet_id)
    } else {
      setOppmSheet(null)
    }
    return () => { setOppmSheet(null) }
  }, [googleSheet?.connected, googleSheet?.spreadsheet_id, setOppmSheet])

  const pushDisabledReason = pushToGoogleSheet.isPending
    ? 'Auto Fill is running…'
    : buttonsDisabled
      ? 'Open this project inside a workspace first.'
      : googleSheetQuery.isLoading
        ? 'Checking Google Sheet state…'
        : !googleSheet?.connected
          ? 'Link a Google Sheet before using Auto Fill.'
          : !googleSheet.backend_configured
            ? (googleSheet.backend_configuration_error || 'Google Sheets write access not configured.')
            : null
  const pushDisabled = !!pushDisabledReason

  /* auto-init */
  useEffect(() => {
    if (hasLinkedSheet) {
      setEditorMode('google')
    } else {
      setEditorMode('app')
      if (sheetData.length === 0 && scaffoldQuery.data?.sheet_data) {
        setSheetData(scaffoldQuery.data.sheet_data)
        setSheetKey((k) => k + 1)
      }
    }
  }, [hasLinkedSheet, scaffoldQuery.data])

  useEffect(() => {
    const linkedValue = googleSheetQuery.data?.spreadsheet_url ?? googleSheetQuery.data?.spreadsheet_id ?? ''
    setSheetInput(linkedValue)
  }, [googleSheetQuery.data])

  useEffect(() => {
    const handler = () => {
      setSheetRefreshToken((v) => v + 1)
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
    }
    window.addEventListener('oppm-sheet-actions-ran', handler)
    return () => window.removeEventListener('oppm-sheet-actions-ran', handler)
  }, [id, ws?.id, queryClient])

  /* ── Render ── */
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="shrink-0 bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-3">
        <Link
          to={`/projects/${id}`}
          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
          title="Back to project"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>

        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">One Page Project Manager</p>
          <h1 className="text-sm font-bold text-gray-900 truncate">{projectQuery.data?.title || 'OPPM'}</h1>
        </div>

        <div className="flex items-center rounded-lg border border-gray-200 bg-gray-50 p-0.5">
          <button
            type="button"
            onClick={() => handleSetEditorMode('app')}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              editorMode === 'app' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            App Editor
          </button>
          <button
            type="button"
            onClick={() => handleSetEditorMode('google')}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              editorMode === 'google' ? 'bg-white text-emerald-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Google Sheet
          </button>
        </div>

        <button
          type="button"
          onClick={() => setShowControlPanel((v) => !v)}
          className="p-1.5 rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
          title={showControlPanel ? 'Hide controls' : 'Show controls'}
        >
          {showControlPanel ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </header>

      {/* Collapsible control bar */}
      {showControlPanel && (
        <div className="shrink-0 bg-white border-b border-gray-200 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-700">
              {editorMode === 'app' ? 'App Editor' : hasLinkedSheet ? `Linked: ${googleSheet?.spreadsheet_id}` : 'No linked sheet'}
            </span>
            {googleSheet?.service_account_email && (
              <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-xs text-blue-700">
                Share with {googleSheet.service_account_email}
              </span>
            )}
            {actionNotice && (
              <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs text-gray-700">
                {actionNotice}
              </span>
            )}
            <div className="flex-1" />

            {editorMode === 'google' && !hasLinkedSheet && (
              <>
                <input
                  value={sheetInput}
                  onChange={(e) => setSheetInput(e.target.value)}
                  placeholder="Google Sheet URL or ID"
                  className="w-64 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs text-gray-900 outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => saveGoogleSheetLink.mutate()}
                  disabled={buttonsDisabled || saveGoogleSheetLink.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {saveGoogleSheetLink.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Link2 className="h-3 w-3" />}
                  Save Link
                </button>
              </>
            )}

            <div className="group relative inline-flex">
              <button
                type="button"
                onClick={() => pushToGoogleSheet.mutate()}
                disabled={pushDisabled}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {pushToGoogleSheet.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
                Auto Fill
              </button>
              {pushDisabledReason && (
                <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-72 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700 shadow-lg group-hover:block">
                  {pushDisabledReason}
                </div>
              )}
            </div>

            {editorMode === 'google' && linkedSheetUrl && (
              <button
                type="button"
                onClick={() => window.open(linkedSheetUrl, '_blank', 'noopener,noreferrer')}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <ExternalLink className="h-3 w-3" />
                Open
              </button>
            )}

            {editorMode === 'google' && hasLinkedSheet && (
              <button
                type="button"
                onClick={() => unlinkGoogleSheet.mutate()}
                disabled={unlinkGoogleSheet.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                {unlinkGoogleSheet.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Unplug className="h-3 w-3" />}
                Unlink
              </button>
            )}
          </div>
        </div>
      )}

      {/* Main content — fills remaining viewport */}
      <main className="flex-1 min-h-0 overflow-hidden">
        {editorMode === 'app' ? (
          <div className="h-full w-full bg-white">
            {patchedSheetData.length > 0 ? (
              <Workbook
                key={sheetKey}
                ref={sheetRef}
                data={patchedSheetData}
                allowEdit={true}
                showToolbar={true}
                showFormulaBar={true}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                onChange={(data: any[]) => { if (data.length > 0) setSheetData(data) }}
                onOp={() => {}}
              />
            ) : (
              <div className="flex h-full items-center justify-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                <span className="text-sm text-gray-400">Loading scaffold…</span>
              </div>
            )}
          </div>
        ) : !hasLinkedSheet ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center max-w-md px-6">
              <h2 className="text-lg font-semibold text-gray-900">No linked Google Sheet</h2>
              <p className="mt-2 text-sm text-gray-600">
                Link a Google Sheet to edit the live OPPM form, or switch to App Editor to work locally.
              </p>
              <div className="mt-4 flex justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowControlPanel(true)}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Link Sheet
                </button>
                <button
                  type="button"
                  onClick={() => handleSetEditorMode('app')}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  App Editor
                </button>
              </div>
            </div>
          </div>
        ) : previewSrc ? (
          <iframe
            key={previewSrc}
            title="Linked Google Sheet"
            src={previewSrc}
            className="h-full w-full border-0"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="flex h-full items-center justify-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
            <span className="text-sm text-gray-400">Preparing Google Sheet…</span>
          </div>
        )}
      </main>
    </div>
  )
}
