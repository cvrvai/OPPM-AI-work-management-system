/**
 * OPPMView — minimal scaffold workspace.
 *
 * This phase intentionally removes the current OPPM feature flows
 * (saved template loading, AI fill, download/export, guide/tool controls)
 * to focus on rebuilding layout structure step-by-step.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, ExternalLink, FileImage, Link2, Loader2, Send, ScanLine, Sparkles, Unplug, X, CloudDownload } from 'lucide-react'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { useChatContext } from '@/hooks/useChatContext'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import { api } from '@/lib/api'
import { fetchWithSessionRetry } from '@/lib/sessionClient'
import { buildOppmScratchSheet } from '@/lib/oppmSheetBuilder'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatStore } from '@/stores/chatStore'

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
  diagnostics?: {
    mapping?: {
      source?: string
      resolved_fields?: Record<string, {
        source?: string
        target?: string
      }>
      task_anchor?: {
        column?: string
        first_row?: number
      }
    }
    writes?: {
      skipped?: number
    }
  }
}

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

// ── OCR fill types ────────────────────────────────────────────────────────
interface OcrFillTaskItem {
  index: string
  title: string
  deadline?: string | null
  status?: string | null
  is_sub: boolean
}

interface OcrFillResponse {
  fills: Record<string, string | null>
  tasks: OcrFillTaskItem[]
  ocr_raw_text: string
  ocr_fields: Record<string, string>
}

type OcrStage = 'idle' | 'scanning' | 'mapping' | 'done' | 'error'

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
  return `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit?rm=minimal&single=true&widget=true&headers=false`
}

// ══════════════════════════════════════════════════════════════
// Blank OPPM template (Fortune Sheet format)
// ══════════════════════════════════════════════════════════════
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function createBlankOppmTemplate(): any[] {
  return buildOppmScratchSheet()
}

// ══════════════════════════════════════════════════════════════
// Border override merge helper
// ══════════════════════════════════════════════════════════════

/** FortuneSheet border style number mapping */
const BORDER_STYLE_MAP: Record<string, number> = {
  thin: 1,
  hair: 2,
  dotted: 3,
  dashed: 4,
  medium_dash_dot: 5,
  medium: 8,
  double: 7,
  thick: 9,
  medium_dashed: 10,
  slant_dash_dot: 11,
  none: 0,
}

const SIDE_KEYS: Record<string, string> = {
  top: 't',
  bottom: 'b',
  left: 'l',
  right: 'r',
}

interface BorderOverride {
  cell_row: number
  cell_col: number
  side: string
  style: string
  color: string
}

/**
 * Merge AI/user border overrides into a FortuneSheet sheet's config.borderInfo.
 * Overrides are applied ON TOP of existing borders (last-write-wins per cell side).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mergeBorderOverrides(sheet: any[], overrides: BorderOverride[]): any[] {
  if (!sheet || sheet.length === 0 || !overrides || overrides.length === 0) {
    return sheet
  }

  const patched = sheet.map((s) => {
    if (!s.config) return s
    const existing: any[] = s.config.borderInfo || []
    const existingMap = new Map<string, any>()

    // Index existing borders by "row_col_side"
    for (const bi of existing) {
      if (bi.rangeType === 'cell' && bi.value) {
        const v = bi.value
        for (const side of ['l', 'r', 't', 'b']) {
          if (v[side]) {
            existingMap.set(`${v.row_index}_${v.col_index}_${side}`, bi)
          }
        }
      }
    }

    // Apply overrides
    for (const o of overrides) {
      const sideKey = SIDE_KEYS[o.side]
      if (!sideKey) continue
      const styleNum = BORDER_STYLE_MAP[o.style] ?? 1

      const mapKey = `${o.cell_row}_${o.cell_col}_${sideKey}`
      const existingBi = existingMap.get(mapKey)

      if (existingBi) {
        // Mutate existing borderInfo entry
        existingBi.value[sideKey] = { style: styleNum, color: o.color }
      } else {
        // Create new cell-level borderInfo entry with just this side
        const newBi = {
          rangeType: 'cell',
          value: {
            row_index: o.cell_row,
            col_index: o.cell_col,
            [sideKey]: { style: styleNum, color: o.color },
          },
        }
        existing.push(newBi)
        existingMap.set(mapKey, newBi)
      }
    }

    return {
      ...s,
      config: {
        ...s.config,
        borderInfo: existing,
      },
    }
  })

  return patched
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
  useChatContext('project', id)

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
  const [inAppEditMode, setInAppEditMode] = useState(false)
  // Ref so the sheet-load effect can check edit mode without adding it as a dependency
  const inAppEditModeRef = useRef(false)
  useEffect(() => { inAppEditModeRef.current = inAppEditMode }, [inAppEditMode])
  const [showDraftComposer, setShowDraftComposer] = useState(false)
  const [draftBrief, setDraftBrief] = useState('')
  const [pendingDraft, setPendingDraft] = useState<SuggestPlanResponse | null>(null)
  const [showControlPanel, setShowControlPanel] = useState(false)

  // OCR Import state
  const [showOcrPanel, setShowOcrPanel] = useState(false)
  const [ocrFile, setOcrFile] = useState<File | null>(null)
  const [ocrStage, setOcrStage] = useState<OcrStage>('idle')
  const [ocrError, setOcrError] = useState<string | null>(null)
  const [ocrResult, setOcrResult] = useState<OcrFillResponse | null>(null)
  const [showOcrRawText, setShowOcrRawText] = useState(false)
  const [isFetchingLinkedSheet, setIsFetchingLinkedSheet] = useState(false)
  const ocrInputRef = React.useRef<HTMLInputElement>(null)

  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

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

  interface AgentFillResponse {
    message: string
    tool_calls: Array<{
      tool: string
      input: Record<string, unknown>
      result: Record<string, unknown>
      success: boolean
      error?: string | null
    }>
    updated_entities: string[]
    iterations: number
    low_confidence: boolean
  }

  // Streaming agent fill (SSE). The blocking endpoint is kept on the backend
  // for callers that don't need progress, but this UI uses the streaming
  // variant so the user sees each tool call as it happens and the gateway
  // doesn't time out on long runs.
  const agentFill = useMutation({
    mutationFn: async () => {
      if (!id) throw new Error('No project selected')
      const path = `${wsPath}/projects/${id}/ai/oppm-agent-fill/stream`
      const res = await fetchWithSessionRetry(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Agent fill failed')
      }
      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response body')
      const decoder = new TextDecoder()
      let buffer = ''
      let final: AgentFillResponse | null = null
      const seenEntities = new Set<string>()
      let toolsRun = 0

      const invalidate = (entities: string[]) => {
        for (const e of entities) seenEntities.add(e)
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          let event = 'message'
          let dataStr = ''
          for (const line of part.split('\n')) {
            if (line.startsWith('event: ')) event = line.slice(7).trim()
            else if (line.startsWith('data: ')) dataStr = line.slice(6).trim()
          }
          if (!dataStr) continue
          let payload: Record<string, unknown>
          try { payload = JSON.parse(dataStr) } catch { continue }

          if (event === 'tool_call') {
            toolsRun += 1
            const toolName = (payload.tool as string) || 'tool'
            const ok = payload.success !== false
            setActionNotice(
              `Agent fill: ${ok ? '✓' : '✗'} ${toolName} (${toolsRun} call${toolsRun === 1 ? '' : 's'} so far)`
            )
            const entities = (payload.updated_entities as string[] | undefined) ?? []
            if (entities.length) invalidate(entities)
          } else if (event === 'message') {
            final = payload as unknown as AgentFillResponse
            invalidate(final.updated_entities ?? [])
          } else if (event === 'error') {
            throw new Error((payload.detail as string) || 'Agent fill failed')
          }
        }
      }

      if (!final) throw new Error('Stream ended without a final message')
      return { ...final, updated_entities: Array.from(seenEntities) }
    },
    onSuccess: (data) => {
      const entitySummary = data.updated_entities.length > 0
        ? ` Updated: ${data.updated_entities.join(', ')}.`
        : ''
      setActionNotice(
        `Agent fill complete.${entitySummary} Iterations: ${data.iterations}. Pushing to Google Sheet…`
      )
      queryClient.invalidateQueries({ queryKey: ['oppm-google-sheet', id, ws?.id] })
      // Auto-push so the sheet reflects what the agent just wrote — the
      // intelligence service deliberately defers this (it has no Sheets
      // credentials), so without this chain the user sees stale numbering
      // from earlier OCR/AI-Draft pushes even though the DB is now clean.
      pushToGoogleSheet.mutate()
    },
    onError: (error: Error) => setActionNotice(error.message),
  })

  // ── OCR upload mutation ────────────────────────────────────────────────
  const uploadOcrForm = useMutation({
    mutationFn: async (file: File) => {
      setOcrStage('scanning')
      setOcrError(null)
      setOcrResult(null)
      const form = new FormData()
      form.append('file', file)
      // Stage 1 completes inside the backend; we show 'mapping' optimistically
      // after a short delay so the user sees both stage labels.
      const timer = setTimeout(() => setOcrStage('mapping'), 4000)
      try {
        const result = await api.postFormData<OcrFillResponse>(
          `${wsPath}/projects/${id}/ai/ocr-fill`,
          form,
        )
        clearTimeout(timer)
        return result
      } catch (err) {
        clearTimeout(timer)
        throw err
      }
    },
    onSuccess: (data) => {
      setOcrStage('done')
      setOcrResult(data)
      setActionNotice('OCR complete — review the detected fields below and apply them to the OPPM.')
    },
    onError: (err: Error) => {
      setOcrStage('error')
      setOcrError(err.message)
    },
  })

  const handleScanLinkedSheet = async () => {
    if (!googleSheet?.spreadsheet_id) return
    setIsFetchingLinkedSheet(true)
    try {
      // 1. Fetch the linked sheet as XLSX blob from the core service
      const blob = await api.getBlob(`${wsPath}/projects/${id}/oppm/google-sheet/xlsx`)
      // 2. Convert to a File object
      const file = new File([blob], `GoogleSheet_${googleSheet.spreadsheet_id}.xlsx`, {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      setOcrFile(file)
      // 3. Submit to OCR
      uploadOcrForm.mutate(file)
    } catch (err: unknown) {
      setOcrStage('error')
      setOcrError(err instanceof Error ? err.message : 'Failed to download linked Google Sheet')
    } finally {
      setIsFetchingLinkedSheet(false)
    }
  }

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

  const handleToggleEditMode = async () => {
    if (hasLinkedSheet) {
      if (linkedSheetUrl) {
        window.open(linkedSheetUrl, '_blank', 'noopener,noreferrer')
      }
      return
    }

    if (inAppEditMode) {
      setInAppEditMode(false)
      return
    }

    setSheetData(createBlankOppmTemplate())
    setSheetKey((k) => k + 1)
    setInAppEditMode(true)
  }

  const handleOpenBlankTemplate = () => {
    setSheetData(createBlankOppmTemplate())
    setSheetKey((k) => k + 1)
    setInAppEditMode(true)
  }

  const googleSheet = googleSheetQuery.data
  const linkedSheetUrl = googleSheet?.spreadsheet_url ?? ''
  const linkedSpreadsheetId = googleSheet?.spreadsheet_id ?? extractSpreadsheetId(sheetInput)
  const embedPreviewUrl = getGoogleSheetEmbedUrl(linkedSpreadsheetId)
  const previewSrc = embedPreviewUrl ? `${embedPreviewUrl}${embedPreviewUrl.includes('?') ? '&' : '?'}refresh=${sheetRefreshToken}` : null
  const buttonsDisabled = !ws || !id
  const hasLinkedSheet = !!googleSheet?.connected

  // Merge border overrides into the FortuneSheet data before rendering
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

  const handleOpenLinkedSheet = () => {
    if (!linkedSheetUrl) return
    window.open(linkedSheetUrl, '_blank', 'noopener,noreferrer')
  }

  const primaryNotice = actionNotice ?? googleSheet?.backend_configuration_error ?? null
  const primaryNoticeTone: Exclude<SheetTone, 'success'> = actionNotice
    ? 'info'
    : googleSheet?.backend_configuration_error
      ? 'warning'
      : 'neutral'
  const pushToGoogleSheetDisabledReason = pushToGoogleSheet.isPending
    ? 'Push AI Fill is already running.'
    : buttonsDisabled
      ? 'Open this project inside a workspace before pushing data to Google Sheets.'
      : googleSheetQuery.isLoading
        ? 'Checking the linked Google Sheet state before enabling Push AI Fill.'
        : !googleSheet?.connected
          ? 'Link a Google Sheet and click Save Link before using Push AI Fill.'
          : !googleSheet.backend_configured
            ? (googleSheet.backend_configuration_error || 'Google Sheets write access is not configured on the backend yet.')
            : null
  const pushToGoogleSheetDisabled = !!pushToGoogleSheetDisabledReason

      useEffect(() => {
        if (!hasLinkedSheet) {
          setShowControlPanel(true)
        }
      }, [hasLinkedSheet])

  useEffect(() => {
    if (hasLinkedSheet && inAppEditMode) {
      setInAppEditMode(false)
    }
  }, [hasLinkedSheet, inAppEditMode])

  useEffect(() => {
    if (!ws || !id || !googleSheet?.connected) {
      if (!inAppEditModeRef.current) setSheetData([])
      setSheetLoadState('idle')
      setSheetLoadError(null)
      return
    }

    if (!googleSheet.backend_configured) {
      if (!inAppEditModeRef.current) setSheetData([])
      setSheetLoadState('preview')
      setSheetLoadError(googleSheet.backend_configuration_error || 'Google integration is not configured on the backend.')
      return
    }

    if (!inAppEditModeRef.current) {
      setSheetData([])
    }
    setSheetLoadError(null)
    // Keep linked sheets on the stable Google preview by default.
    // The Fortune workbook path is reserved for explicit edit-mode entry.
    setSheetLoadState('preview')
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

          {hasLinkedSheet ? (
            <button
              type="button"
              onClick={handleOpenLinkedSheet}
              disabled={!linkedSheetUrl}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-600 px-2.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ExternalLink className="h-3 w-3" />
              Open in New Tab
            </button>
          ) : (
            <button
              type="button"
              onClick={handleToggleEditMode}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                inAppEditMode
                  ? 'border-blue-300 bg-blue-600 text-white hover:bg-blue-700'
                  : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
              }`}
            >
              {inAppEditMode ? 'Exit Editor' : 'Edit in App'}
            </button>
          )}
        </div>

        <div className="pb-3">
          <div className="rounded-2xl border border-gray-200 bg-gradient-to-br from-white via-slate-50 to-blue-50/60 px-4 py-4 shadow-sm">
            {showControlPanel ? (
              <div className="rounded-xl border border-blue-100 bg-white px-4 py-4 shadow-sm">
                <div className="flex flex-col gap-3">
                  <input
                    value={sheetInput}
                    onChange={(e) => setSheetInput(e.target.value)}
                    placeholder="Google Sheet URL or Spreadsheet ID"
                    className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500"
                  />

                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-gray-700">
                      {googleSheetQuery.isLoading
                        ? 'Loading...'
                        : googleSheet?.connected
                          ? `Linked: ${googleSheet.spreadsheet_id}`
                          : 'No linked sheet'}
                    </span>
                    {googleSheet?.service_account_email ? (
                      <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-blue-700">
                        Share with {googleSheet.service_account_email}
                      </span>
                    ) : null}
                    {!googleSheet?.backend_configured ? (
                      <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-800">
                        Google write not configured
                      </span>
                    ) : null}
                    {pushToGoogleSheetDisabledReason ? (
                      <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-800">
                        Push unavailable
                      </span>
                    ) : null}
                  </div>

                  {primaryNotice ? (
                    <div className={`rounded-lg border px-3 py-2 text-xs ${
                      primaryNoticeTone === 'warning'
                        ? 'border-amber-200 bg-amber-50 text-amber-800'
                        : 'border-blue-100 bg-slate-50 text-slate-700'
                    }`}>
                      {primaryNotice}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full border border-blue-100 bg-white px-2.5 py-1 text-gray-700">
                  {hasLinkedSheet ? `Linked: ${googleSheet?.spreadsheet_id}` : 'No linked sheet'}
                </span>
                {googleSheet?.service_account_email ? (
                  <span className="rounded-full border border-blue-100 bg-white px-2.5 py-1 text-blue-700">
                    {googleSheet.service_account_email}
                  </span>
                ) : null}
                {primaryNotice ? (
                  <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-gray-700">
                    {primaryNotice}
                  </span>
                ) : null}
              </div>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                id="ocr-import-toggle-btn"
                type="button"
                onClick={() => setShowOcrPanel((v) => !v)}
                disabled={buttonsDisabled}
                className="inline-flex items-center gap-2 rounded-lg border border-violet-300 bg-violet-50 px-3 py-2 text-sm font-medium text-violet-700 transition-colors hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ScanLine className="h-4 w-4" />
                {showOcrPanel ? 'Hide OCR Import' : 'OCR Import'}
              </button>

              <button
                type="button"
                onClick={() => setShowDraftComposer((value) => !value)}
                disabled={buttonsDisabled}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                {pendingDraft ? 'Review Draft' : 'AI Draft'}
              </button>

              {!hasLinkedSheet ? (
                <button
                  type="button"
                  onClick={() => saveGoogleSheetLink.mutate()}
                  disabled={buttonsDisabled || saveGoogleSheetLink.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saveGoogleSheetLink.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                  Save Link
                </button>
              ) : null}

              <div className="group relative inline-flex">
                <div
                  title={pushToGoogleSheetDisabledReason ?? undefined}
                  className={`inline-flex ${pushToGoogleSheetDisabled ? 'cursor-not-allowed' : ''}`}
                >
                  <button
                    type="button"
                    onClick={() => pushToGoogleSheet.mutate()}
                    disabled={pushToGoogleSheetDisabled}
                    aria-describedby={pushToGoogleSheetDisabledReason ? 'push-ai-fill-disabled-reason' : undefined}
                    className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {pushToGoogleSheet.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    Auto Fill
                  </button>
                </div>
                {pushToGoogleSheetDisabledReason ? (
                  <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-80 rounded-xl border border-emerald-200 bg-white px-3 py-2 text-xs text-gray-700 shadow-lg group-hover:block">
                    {pushToGoogleSheetDisabledReason}
                  </div>
                ) : null}
              </div>

              <div className="group relative inline-flex">
                <button
                  type="button"
                  onClick={() => agentFill.mutate()}
                  disabled={!id || agentFill.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {agentFill.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Agent Fill
                </button>
                <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-80 rounded-xl border border-violet-200 bg-white px-3 py-2 text-xs text-gray-700 shadow-lg group-hover:block">
                  Runs the OPPM skill agent end-to-end: writes header, timeline, owners, sub-objectives, risks, costs — then pushes to Google Sheets.
                </div>
              </div>

              {!googleSheet?.backend_configured ? (
                <Link
                  to="/settings?tab=googleSheets"
                  className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100"
                >
                  Setup Google Write
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
                Remove Link
              </button>
            </div>

            {pushToGoogleSheetDisabledReason ? (
              <p id="push-ai-fill-disabled-reason" className="sr-only">
                Push AI Fill is unavailable: {pushToGoogleSheetDisabledReason}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3">
        {/* ── OCR Import panel ──────────────────────────────────────── */}
        {showOcrPanel ? (
          <div className="mb-4 rounded-2xl border border-violet-200 bg-white shadow-sm overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b border-violet-100 bg-gradient-to-r from-violet-50 to-indigo-50 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-600 shadow-sm">
                  <ScanLine className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-violet-500">Two-Stage AI Pipeline</p>
                  <h2 className="text-sm font-bold text-gray-900">OCR Form Import</h2>
                </div>
              </div>
              <button
                type="button"
                onClick={() => { setShowOcrPanel(false); setOcrFile(null); setOcrStage('idle'); setOcrResult(null); setOcrError(null) }}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-violet-100 hover:text-violet-700 transition-colors"
                aria-label="Close OCR panel"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Model info strip */}
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 font-semibold text-violet-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-500"></span>
                  Stage 1 · gemma4:31b-cloud (OCR)
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 font-semibold text-indigo-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-500"></span>
                  Stage 2 · Workspace Ollama model (Fill)
                </span>
              </div>

              {/* Drop zone */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => ocrInputRef.current?.click()}
                onKeyDown={(e) => e.key === 'Enter' && ocrInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  const dropped = e.dataTransfer.files[0]
                  if (dropped) setOcrFile(dropped)
                }}
                className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-violet-200 bg-violet-50/40 px-6 py-8 text-center transition-colors hover:border-violet-400 hover:bg-violet-50"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white shadow-sm border border-violet-100">
                  <FileImage className="h-6 w-6 text-violet-500" />
                </div>
                {ocrFile ? (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-gray-900">{ocrFile.name}</p>
                    <p className="text-xs text-gray-500">{(ocrFile.size / 1024).toFixed(1)} KB · Click to change</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-gray-700">Drop your OPPM form here</p>
                    <p className="text-xs text-gray-500">PNG, JPEG, WEBP, or PDF · Max 20 MB</p>
                  </div>
                )}
              </div>
              <input
                ref={ocrInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
                className="sr-only"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setOcrFile(f) }}
              />

              {/* Stage progress */}
              {ocrStage !== 'idle' && (
                <div className="rounded-xl border border-violet-100 bg-violet-50/60 px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-2">
                      {/* Stage 1 badge */}
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors ${
                        ocrStage === 'scanning'
                          ? 'bg-violet-600 text-white'
                          : ocrStage === 'mapping' || ocrStage === 'done'
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-gray-100 text-gray-500'
                      }`}>
                        {ocrStage === 'scanning'
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <CheckCircle2 className="h-3 w-3" />}
                        1. OCR Scan
                      </span>
                      {/* Stage 2 badge */}
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors ${
                        ocrStage === 'mapping'
                          ? 'bg-indigo-600 text-white'
                          : ocrStage === 'done'
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-gray-100 text-gray-400'
                      }`}>
                        {ocrStage === 'mapping'
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : ocrStage === 'done'
                            ? <CheckCircle2 className="h-3 w-3" />
                            : null}
                        2. AI Mapping
                      </span>
                    </div>
                    {ocrStage === 'done' && (
                      <span className="text-xs font-semibold text-emerald-700">Complete ✓</span>
                    )}
                    {ocrStage === 'error' && (
                      <span className="text-xs font-semibold text-red-600">Failed</span>
                    )}
                  </div>
                  {ocrError && (
                    <p className="mt-2 text-xs text-red-600">{ocrError}</p>
                  )}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex flex-wrap gap-3">
                <button
                  id="ocr-scan-btn"
                  type="button"
                  disabled={!ocrFile || uploadOcrForm.isPending || isFetchingLinkedSheet || buttonsDisabled}
                  onClick={() => ocrFile && uploadOcrForm.mutate(ocrFile)}
                  className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {uploadOcrForm.isPending
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <ScanLine className="h-4 w-4" />}
                  {uploadOcrForm.isPending ? 'Processing…' : 'Scan File'}
                </button>

                {hasLinkedSheet && (
                  <button
                    type="button"
                    disabled={uploadOcrForm.isPending || isFetchingLinkedSheet || buttonsDisabled}
                    onClick={handleScanLinkedSheet}
                    className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-white px-4 py-2.5 text-sm font-semibold text-violet-700 shadow-sm transition-colors hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isFetchingLinkedSheet
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <CloudDownload className="h-4 w-4" />}
                    {isFetchingLinkedSheet ? 'Downloading…' : 'Scan Linked Sheet'}
                  </button>
                )}
              </div>

              {/* Results panel */}
              {ocrResult && ocrStage === 'done' && (
                <div className="space-y-3 rounded-xl border border-violet-100 bg-white p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-bold text-gray-900">Detected Fields</p>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                      {Object.values(ocrResult.fills).filter(Boolean).length} fields mapped
                    </span>
                  </div>

                  {/* Fills table */}
                  <div className="overflow-hidden rounded-lg border border-gray-200">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left font-semibold text-gray-500 uppercase tracking-wider">OPPM Field</th>
                          <th className="px-3 py-2 text-left font-semibold text-gray-500 uppercase tracking-wider">Detected Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {Object.entries(ocrResult.fills)
                          .filter(([k]) => k !== 'project_leader_member_id')
                          .map(([key, value]) => (
                            <tr key={key} className={value ? 'bg-white' : 'bg-gray-50'}>
                              <td className="px-3 py-2 font-medium text-gray-700">
                                {key.replace(/_/g, ' ')}
                              </td>
                              <td className="px-3 py-2 text-gray-900">
                                {value || <span className="italic text-gray-400">— not detected</span>}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Task rows */}
                  {ocrResult.tasks.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-gray-700">Task Rows Detected ({ocrResult.tasks.length})</p>
                      <div className="space-y-1">
                        {ocrResult.tasks.map((task, i) => (
                          <div
                            key={`${task.index}-${i}`}
                            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
                              task.is_sub ? 'ml-4 bg-gray-50 text-gray-700' : 'bg-violet-50 font-semibold text-violet-900'
                            }`}
                          >
                            <span className="w-8 shrink-0 font-mono text-gray-400">{task.index}</span>
                            <span className="flex-1 truncate">{task.title}</span>
                            {task.deadline && (
                              <span className="shrink-0 rounded bg-blue-100 px-1.5 py-0.5 text-blue-700">{task.deadline}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Raw OCR toggle */}
                  <button
                    type="button"
                    onClick={() => setShowOcrRawText((v) => !v)}
                    className="text-xs font-medium text-violet-600 hover:underline"
                  >
                    {showOcrRawText ? 'Hide raw OCR text' : 'Show raw OCR text'}
                  </button>
                  {showOcrRawText && (
                    <pre className="max-h-48 overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-3 text-[11px] leading-relaxed text-gray-700 whitespace-pre-wrap">
                      {ocrResult.ocr_raw_text || '(no raw text returned)'}
                    </pre>
                  )}
                </div>
              )}
            </div>
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

        {!hasLinkedSheet && inAppEditMode ? (
          <div className="space-y-2">
            <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600">
              Blank in-app editor only. Link or open a real Google Sheet to edit the live form safely.
            </div>

            <div
              className="bg-white border border-gray-300 rounded-lg overflow-hidden"
              style={{ height: 'calc(100vh - 160px)', minHeight: 520 }}
            >
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
                <div className="flex items-center justify-center gap-3 h-full">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                  <span className="text-sm text-gray-400">Preparing editor…</span>
                </div>
              )}
            </div>
          </div>
        ) : !hasLinkedSheet ? (
          <MessagePanel
            title="No linked Google Sheet yet"
            description="Link a Google Sheet above to work on the real OPPM form in Google Sheets, or click 'Edit in App' to sketch a blank template locally."
            tone="neutral"
            actions={(
              <button
                type="button"
                onClick={handleToggleEditMode}
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                Edit blank OPPM in App
              </button>
            )}
          />
        ) : sheetLoadState === 'preview' && previewSrc ? (
          <div className="space-y-4">
            <div className="overflow-hidden rounded-xl border border-sky-200 bg-white shadow-sm">
              <div className="border-b border-sky-100 bg-sky-50 px-4 py-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-sky-900">Live Google Sheet Editor</p>
                  <p className="mt-1 text-xs text-sky-800">
                    Edit the linked Google Sheet directly inside this page. Changes are written by Google Sheets in real time, so the original form stays intact.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleOpenLinkedSheet}
                  disabled={!linkedSheetUrl}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  <ExternalLink className="h-3 w-3" />
                  Open in New Tab
                </button>
              </div>
              <iframe
                key={previewSrc}
                title="Linked Google Sheet Editor"
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
            description="A linked Google Sheet exists, but the app could not build an embeddable preview for it."
            detail={sheetLoadError || 'Open the linked Google Sheet directly to edit the live form.'}
            tone="info"
            actions={linkedSheetUrl ? (
              <button
                type="button"
                onClick={handleOpenLinkedSheet}
                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
              >
                Open in Google Sheets
              </button>
            ) : undefined}
          />
        ) : sheetLoadState === 'error' ? (
          <MessagePanel
            title="Linked Google Sheet unavailable"
            description={sheetLoadError || 'The linked Google Sheet could not be prepared inside the app.'}
            tone="danger"
            actions={(
              <>
                <button
                  type="button"
                  onClick={() => setSheetRefreshToken((value) => value + 1)}
                  className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
                >
                  Retry Preview
                </button>
                <button
                  type="button"
                  onClick={handleOpenLinkedSheet}
                  disabled={!linkedSheetUrl}
                  className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50"
                >
                  Open in Google Sheets
                </button>
              </>
            )}
          />
        ) : patchedSheetData.length > 0 ? (
          <div
            className="bg-white border border-gray-300 rounded-lg overflow-hidden"
            style={{ height: 'calc(100vh - 120px)', minHeight: 520 }}
          >
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
