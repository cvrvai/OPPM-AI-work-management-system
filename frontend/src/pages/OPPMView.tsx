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
    oppm?: number
    summary: number
    tasks: number
    members: number
  }
}

const LINKED_SHEET_XLSX_TIMEOUT_MS = 8000

interface SuggestedPlanTask {
  title: string
  priority?: string | null
  suggested_weeks: string[]
  subtasks: string[]
}

interface SuggestedPlanObjective {
  title: string
  suggested_weeks: string[]
  tasks: SuggestedPlanTask[]
}

interface SuggestedPlanHeader {
  project_leader?: string | null
  project_objective?: string | null
  deliverable_output?: string | null
  completed_by_text?: string | null
  people_count?: number | null
}

interface SuggestPlanResponse {
  header: SuggestedPlanHeader
  suggested_objectives: SuggestedPlanObjective[]
  explanation: string
  commit_token: string
  existing_task_count: number
}

interface CommitPlanResult {
  count: number
  objectives_created: number
  objectives_updated: number
  tasks_created: number
  tasks_updated: number
  timeline_entries_upserted: number
}

interface OppmTaskSnapshot {
  id: string
  title: string
  status?: string | null
}

interface OppmObjectiveSnapshot {
  id: string
  title: string
  tasks?: OppmTaskSnapshot[]
}

interface OppmProjectSnapshot {
  objective_summary?: string | null
  deliverable_output?: string | null
}

interface OppmHeaderSnapshot {
  project_leader_text?: string | null
  completed_by_text?: string | null
  people_count?: number | null
}

interface OppmCombinedSnapshot {
  project?: OppmProjectSnapshot
  header?: OppmHeaderSnapshot
  objectives?: OppmObjectiveSnapshot[]
  timeline?: Array<unknown>
}

type SheetTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

function StatusTile({
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  label: string
  value: string
  detail?: string
  tone?: SheetTone
}) {
  const toneClasses: Record<SheetTone, string> = {
    neutral: 'border-gray-200 bg-gray-50 text-gray-700',
    info: 'border-sky-200 bg-sky-50 text-sky-700',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    warning: 'border-amber-200 bg-amber-50 text-amber-700',
    danger: 'border-red-200 bg-red-50 text-red-700',
  }

  return (
    <div className={`rounded-xl border p-3 ${toneClasses[tone]}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-current/70">{label}</p>
      <p className="mt-1 text-sm font-semibold text-current">{value}</p>
      {detail ? <p className="mt-1 text-xs text-current/80">{detail}</p> : null}
    </div>
  )
}

function MessagePanel({
  title,
  description,
  detail,
  tone = 'neutral',
  actions,
}: {
  title: string
  description: string
  detail?: string | null
  tone?: Exclude<SheetTone, 'success'>
  actions?: React.ReactNode
}) {
  const wrapperClasses: Record<Exclude<SheetTone, 'success'>, string> = {
    neutral: 'border-gray-200 bg-white text-gray-900',
    info: 'border-sky-200 bg-sky-50 text-sky-900',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    danger: 'border-red-200 bg-red-50 text-red-900',
  }

  const bodyClasses: Record<Exclude<SheetTone, 'success'>, string> = {
    neutral: 'text-gray-600',
    info: 'text-sky-800',
    warning: 'text-amber-800',
    danger: 'text-red-700',
  }

  return (
    <div className={`rounded-xl border px-6 py-8 text-center ${wrapperClasses[tone]}`}>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className={`mx-auto mt-2 max-w-2xl text-sm ${bodyClasses[tone]}`}>{description}</p>
      {detail ? <p className={`mx-auto mt-2 max-w-2xl text-sm ${bodyClasses[tone]}/90`}>{detail}</p> : null}
      {actions ? <div className="mt-4 flex flex-wrap justify-center gap-2">{actions}</div> : null}
    </div>
  )
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
  const [sheetLoadState, setSheetLoadState] = useState<'idle' | 'loading' | 'ready' | 'preview' | 'error'>('idle')
  const [sheetLoadError, setSheetLoadError] = useState<string | null>(null)
  const [sheetRefreshToken, setSheetRefreshToken] = useState(0)
  const [showDraftComposer, setShowDraftComposer] = useState(false)
  const [draftBrief, setDraftBrief] = useState('')
  const [pendingDraft, setPendingDraft] = useState<SuggestPlanResponse | null>(null)
  const [showControlPanel, setShowControlPanel] = useState(false)
  const [showNativeSnapshot, setShowNativeSnapshot] = useState(true)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  const googleSheetQuery = useQuery({
    queryKey: ['oppm-google-sheet', id, ws?.id],
    queryFn: () => api.get<GoogleSheetLinkState>(`${wsPath}/projects/${id}/oppm/google-sheet`),
    enabled: !!ws && !!id,
  })

  const oppmSnapshotQuery = useQuery({
    queryKey: ['oppm-combined', id, ws?.id],
    queryFn: () => api.get<OppmCombinedSnapshot>(`${wsPath}/projects/${id}/oppm`),
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
      const oppmInfo = typeof data.rows_written.oppm === 'number'
        ? ` OPPM rows: ${data.rows_written.oppm}.`
        : ''
      setActionNotice(
        `Pushed AI-filled data to Google Sheets.${oppmInfo} Summary: ${data.rows_written.summary}, tasks: ${data.rows_written.tasks}, members: ${data.rows_written.members}. Check tabs OPPM, OPPM Summary, OPPM Tasks, and OPPM Members for updated values.`
      )
      setSheetRefreshToken((value) => value + 1)
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const generateOppmDraft = useMutation({
    mutationFn: (description: string) =>
      api.post<SuggestPlanResponse>(`${wsPath}/projects/${id}/ai/suggest-plan`, { description }),
    onSuccess: (data) => {
      const normalizedDraft: SuggestPlanResponse = {
        ...data,
        header: data.header ?? {},
        suggested_objectives: (data.suggested_objectives ?? []).map((objective) => ({
          ...objective,
          tasks: objective.tasks ?? [],
        })),
        existing_task_count: data.existing_task_count ?? 0,
      }
      setPendingDraft(normalizedDraft)
      setShowDraftComposer(true)
      setActionNotice('AI draft generated. Review it below and apply it when ready.')
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const applyOppmDraft = useMutation({
    mutationFn: (commitToken: string) =>
      api.post<CommitPlanResult>(`${wsPath}/projects/${id}/ai/suggest-plan/commit`, { commit_token: commitToken }),
    onSuccess: (data) => {
      setPendingDraft(null)
      setShowDraftComposer(false)
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      queryClient.invalidateQueries({ queryKey: ['tasks', id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-timeline', id] })
      setActionNotice(
        `Applied native OPPM draft. Objectives: ${data.objectives_created + data.objectives_updated}, tasks created: ${data.tasks_created}, tasks updated: ${data.tasks_updated}, timeline rows: ${data.timeline_entries_upserted}.`
      )
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  const googleSheet = googleSheetQuery.data
  const linkedSheetUrl = googleSheet?.spreadsheet_url ?? ''
  const linkedSpreadsheetId = googleSheet?.spreadsheet_id ?? extractSpreadsheetId(sheetInput)
  const embedPreviewUrl = getGoogleSheetEmbedUrl(linkedSpreadsheetId)
  const previewSrc = embedPreviewUrl ? `${embedPreviewUrl}${embedPreviewUrl.includes('?') ? '&' : '?'}refresh=${sheetRefreshToken}` : null
  const buttonsDisabled = !ws || !id
  const hasLinkedSheet = !!googleSheet?.connected
  const oppmSnapshot = oppmSnapshotQuery.data
  const snapshotObjectives = oppmSnapshot?.objectives ?? []
  const snapshotTasks = snapshotObjectives.flatMap((objective) => objective.tasks ?? [])
  const snapshotCompletedTasks = snapshotTasks.filter((task) => task.status === 'completed').length
  const primaryNotice = actionNotice ?? googleSheet?.backend_configuration_error ?? null
  const primaryNoticeTone: Exclude<SheetTone, 'success'> = actionNotice
    ? 'info'
    : googleSheet?.backend_configuration_error
      ? 'warning'
      : 'neutral'

      useEffect(() => {
        if (!hasLinkedSheet) {
          setShowControlPanel(true)
        }
      }, [hasLinkedSheet])

  useEffect(() => {
    if (!ws || !id || !googleSheet?.connected) {
      setSheetData([])
      setSheetLoadState('idle')
      setSheetLoadError(null)
      return
    }

    if (!googleSheet.backend_configured) {
      setSheetData([])
      setSheetLoadState('preview')
      setSheetLoadError(googleSheet.backend_configuration_error || 'Google integration is not configured on the backend.')
      return
    }

    let cancelled = false
    setSheetLoadState('loading')
    setSheetLoadError(null)
    const linkedPreviewId = googleSheet?.spreadsheet_id ?? null

    const loadLinkedSheet = async () => {
      try {
        const blob = await Promise.race([
          api.getBlob(`${wsPath}/projects/${id}/oppm/google-sheet/xlsx`),
          new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error('Linked sheet download timed out. Falling back to browser preview.')), LINKED_SHEET_XLSX_TIMEOUT_MS)
          }),
        ])
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
        const message = error instanceof Error ? error.message : 'Failed to load the linked Google Sheet.'
        setSheetLoadError(message)
        setSheetLoadState(linkedPreviewId ? 'preview' : 'error')
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
      <div className="z-30 bg-white border-b border-gray-200 shadow-sm -mx-4 sm:-mx-6 px-4 sm:px-6">
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

          <button
            type="button"
            onClick={() => setShowControlPanel((value) => !value)}
            className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            {showControlPanel ? 'Hide controls' : 'Show controls'}
          </button>
        </div>

        <div className="pb-3">
          <div className="rounded-2xl border border-gray-200 bg-gradient-to-br from-white via-slate-50 to-blue-50/60 px-4 py-4 shadow-sm">
            {showControlPanel ? (
              <div className="grid gap-3">
                <div className="rounded-xl border border-blue-100 bg-white px-4 py-4 shadow-sm">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-700">Sheet Source</p>
                  <label className="mt-2 block text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
                    Google Sheet URL or Spreadsheet ID
                  </label>
                  <input
                    value={sheetInput}
                    onChange={(e) => setSheetInput(e.target.value)}
                    placeholder="https://docs.google.com/spreadsheets/d/... or spreadsheet ID"
                    className="mt-1.5 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500"
                  />
                  <p className="mt-2 text-xs text-gray-600">
                    {googleSheet?.service_account_email
                      ? `Share the target spreadsheet with ${googleSheet.service_account_email} before using Push AI Fill.`
                      : googleSheet?.backend_configuration_error
                        ? 'Backend Google push is unavailable right now, but linked-sheet browser preview can still work.'
                        : 'The backend must be configured with a Google service account before Push AI Fill can run.'}
                  </p>
                <p className="mt-1 text-xs text-gray-600">
                  AI push updates `OPPM Summary`, `OPPM Tasks`, and `OPPM Members` tabs. The original `OPPM` tab remains your template layout unless you edit it directly in Google Sheets.
                </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                    <span className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1">
                      {googleSheetQuery.isLoading
                        ? 'Loading link state...'
                        : googleSheet?.connected
                          ? `Linked spreadsheet: ${googleSheet.spreadsheet_id}`
                          : 'No Google Sheet linked yet'}
                    </span>
                    {linkedSheetUrl ? (
                      <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-blue-700">
                        Existing linked form active
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full border border-blue-100 bg-white px-2.5 py-1 text-gray-700">
                  {hasLinkedSheet ? `Linked: ${googleSheet?.spreadsheet_id}` : 'No linked sheet'}
                </span>
                <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-gray-700">
                  Tasks: {snapshotCompletedTasks}/{snapshotTasks.length} completed
                </span>
              </div>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setShowDraftComposer((value) => !value)}
                disabled={buttonsDisabled}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                {pendingDraft ? 'Review AI Draft' : 'Generate OPPM Draft'}
              </button>

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

              {!googleSheet?.backend_configured ? (
                <Link
                  to="/settings?tab=googleSheets"
                  className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100"
                >
                  Setup Google Sheets Write
                </Link>
              ) : null}

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

            {primaryNotice ? (
              <div className={`mt-3 rounded-xl border px-3 py-2 text-sm ${
                primaryNoticeTone === 'warning'
                  ? 'border-amber-200 bg-amber-50 text-amber-800'
                  : 'border-blue-100 bg-white text-gray-700'
              }`}>
                {primaryNotice}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3">
        {oppmSnapshot ? (
          <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setShowNativeSnapshot((value) => !value)}
                className="text-left"
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Native App Data</p>
                <h2 className="mt-1 text-base font-semibold text-gray-900">Live OPPM data snapshot</h2>
              </button>
              <div className="flex items-center gap-2">
                <div className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700">
                  Objectives: {snapshotObjectives.length} · Tasks: {snapshotTasks.length}
                </div>
                <button
                  type="button"
                  onClick={() => setShowNativeSnapshot((value) => !value)}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  {showNativeSnapshot ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {showNativeSnapshot ? (
              <>
                <p className="mt-2 text-xs text-slate-600">
                  This panel shows real project data stored in the app database. If the linked Google Sheet still shows placeholder text, it means the sheet itself has not been updated yet.
                </p>

                <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                  <StatusTile
                    label="Project Objective"
                    value={oppmSnapshot.project?.objective_summary || 'Not set'}
                    tone="info"
                  />
                  <StatusTile
                    label="Deliverable Output"
                    value={oppmSnapshot.project?.deliverable_output || 'Not set'}
                    tone="neutral"
                  />
                  <StatusTile
                    label="Project Leader"
                    value={oppmSnapshot.header?.project_leader_text || 'Not set'}
                    detail={oppmSnapshot.header?.completed_by_text ? `Completed by: ${oppmSnapshot.header.completed_by_text}` : undefined}
                    tone="neutral"
                  />
                  <StatusTile
                    label="Progress"
                    value={`${snapshotCompletedTasks}/${snapshotTasks.length} tasks completed`}
                    detail={`Timeline rows: ${oppmSnapshot.timeline?.length ?? 0}`}
                    tone={snapshotCompletedTasks > 0 ? 'success' : 'warning'}
                  />
                </div>
              </>
            ) : null}
          </div>
        ) : null}

        {(showDraftComposer || pendingDraft) ? (
          <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-3xl">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Native OPPM Draft</p>
                <h2 className="mt-1 text-lg font-semibold text-gray-900">Generate a native OPPM draft from a business brief</h2>
                <p className="mt-2 text-sm text-gray-600">
                  This creates a preview first, then commits the approved draft into the project, objective, task, and timeline data already stored in the app. Existing task titles are reused when they match.
                </p>
              </div>
              {pendingDraft ? (
                <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
                  Preview ready: {pendingDraft.suggested_objectives.length} objectives · {pendingDraft.existing_task_count} current task(s) considered
                </div>
              ) : null}
            </div>

            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <label className="block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                Business Brief
              </label>
              <textarea
                value={draftBrief}
                onChange={(event) => setDraftBrief(event.target.value)}
                placeholder="Describe the project goal, scope, and any constraints the AI should use when building the native OPPM draft."
                rows={4}
                className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-gray-900 outline-none focus:border-blue-500"
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => generateOppmDraft.mutate(draftBrief.trim())}
                  disabled={buttonsDisabled || !draftBrief.trim() || generateOppmDraft.isPending}
                  className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {generateOppmDraft.isPending ? 'Generating draft...' : pendingDraft ? 'Generate again' : 'Generate draft'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPendingDraft(null)
                    setShowDraftComposer(false)
                  }}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100"
                >
                  Close
                </button>
              </div>
            </div>

            {pendingDraft ? (
              <div className="mt-4 space-y-4">
                <div className="grid gap-3 lg:grid-cols-3">
                  <StatusTile
                    label="Objective"
                    value={pendingDraft.header.project_objective || 'Not set'}
                    detail={pendingDraft.header.deliverable_output || 'Deliverable output not provided by the draft.'}
                    tone="info"
                  />
                  <StatusTile
                    label="Project Leader"
                    value={pendingDraft.header.project_leader || 'Not set'}
                    detail={pendingDraft.header.completed_by_text ? `Completed by: ${pendingDraft.header.completed_by_text}` : 'Completion target not provided.'}
                    tone="neutral"
                  />
                  <StatusTile
                    label="People Count"
                    value={String(pendingDraft.header.people_count ?? 0)}
                    detail={`${pendingDraft.suggested_objectives.reduce((count, objective) => count + objective.tasks.length, 0)} suggested root task(s)`}
                    tone="success"
                  />
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <p className="text-sm font-semibold text-gray-900">Draft Preview</p>
                  {pendingDraft.explanation ? (
                    <p className="mt-2 text-sm text-gray-600">{pendingDraft.explanation}</p>
                  ) : null}
                  <div className="mt-4 space-y-3">
                    {pendingDraft.suggested_objectives.map((objective, objectiveIndex) => (
                      <div key={`${objective.title}-${objectiveIndex}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-gray-900">{objectiveIndex + 1}. {objective.title}</p>
                            <p className="mt-1 text-xs text-gray-500">
                              {objective.tasks.length > 0 ? `${objective.tasks.length} grouped task(s)` : 'No explicit tasks returned in this objective.'}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {objective.suggested_weeks.length > 0 ? objective.suggested_weeks.map((week) => (
                              <span key={`${objective.title}-${week}`} className="rounded-full bg-blue-100 px-2 py-1 text-[11px] font-semibold text-blue-700">
                                {week}
                              </span>
                            )) : (
                              <span className="rounded-full bg-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-600">
                                No weeks suggested
                              </span>
                            )}
                          </div>
                        </div>

                        {objective.tasks.length > 0 ? (
                          <div className="mt-3 space-y-2">
                            {objective.tasks.map((task, taskIndex) => (
                              <div key={`${objective.title}-${task.title}-${taskIndex}`} className="rounded-lg border border-slate-200 bg-white px-3 py-3">
                                <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                                  <div>
                                    <p className="text-sm font-medium text-gray-900">{task.title}</p>
                                    <p className="mt-1 text-xs text-gray-500">
                                      Priority: {task.priority || 'medium'}
                                      {task.subtasks.length > 0 ? ` · ${task.subtasks.length} sub-task(s)` : ''}
                                    </p>
                                  </div>
                                  <div className="flex flex-wrap gap-1">
                                    {(task.suggested_weeks.length > 0 ? task.suggested_weeks : objective.suggested_weeks).map((week) => (
                                      <span key={`${task.title}-${week}`} className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-700">
                                        {week}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                                {task.subtasks.length > 0 ? (
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {task.subtasks.map((subtask, subtaskIndex) => (
                                      <span key={`${task.title}-${subtask}-${subtaskIndex}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600">
                                        {subtask}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => applyOppmDraft.mutate(pendingDraft.commit_token)}
                      disabled={applyOppmDraft.isPending}
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {applyOppmDraft.isPending ? 'Applying draft...' : 'Apply native OPPM draft'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDraft(null)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100"
                    >
                      Discard preview
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {!hasLinkedSheet ? (
          <MessagePanel
            title="No linked Google Sheet yet"
            description="Save a Google Sheet URL or spreadsheet ID above to load that existing form inside the OPPM page. The hardcoded scaffold is no longer the primary display path."
            tone="neutral"
          />
        ) : sheetLoadState === 'loading' ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border border-gray-200 bg-white py-24">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-sm text-gray-500">Loading linked Google Sheet…</span>
          </div>
        ) : sheetLoadState === 'preview' && previewSrc ? (
          <div className="space-y-4">
            <div className="overflow-hidden rounded-xl border border-sky-200 bg-white shadow-sm">
              <div className="border-b border-sky-100 bg-sky-50 px-4 py-3">
                <p className="text-sm font-semibold text-sky-900">Live Browser Preview</p>
                <p className="mt-1 text-xs text-sky-800">
                  This preview is read-only inside the app. Edit the sheet in Google Sheets, then refresh this preview to see the latest content here.
                </p>
              </div>
              <iframe
                key={previewSrc}
                title="Linked Google Sheet Preview"
                src={previewSrc}
                className="h-[70vh] min-h-[520px] w-full border-0 bg-white"
                loading="lazy"
                referrerPolicy="no-referrer"
              />
            </div>
          </div>
        ) : sheetLoadState === 'preview' ? (
          <MessagePanel
            title="Linked Google Sheet Preview Unavailable"
            description="The page is in browser preview mode, but no preview URL could be built from the current Google Sheet link."
            detail={sheetLoadError || 'Save a valid Google Sheet URL or spreadsheet ID to enable live preview inside the OPPM page.'}
            tone="info"
          />
        ) : sheetLoadState === 'error' ? (
          <MessagePanel
            title="Linked Google Sheet unavailable"
            description={sheetLoadError || 'The linked Google Sheet could not be loaded into the app.'}
            tone="danger"
            actions={(
              <>
                <button
                  type="button"
                  onClick={() => setSheetRefreshToken((value) => value + 1)}
                  className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
                >
                  Retry App Render
                </button>
                <button
                  type="button"
                  onClick={() => linkedSheetUrl && window.open(linkedSheetUrl, '_blank', 'noopener,noreferrer')}
                  disabled={!linkedSheetUrl}
                  className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50"
                >
                  Open in Google Sheets
                </button>
              </>
            )}
          />
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
