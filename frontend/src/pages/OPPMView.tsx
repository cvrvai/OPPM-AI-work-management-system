/**
 * OPPMView — Standard One Page Project Manager (Clark Campbell OPPM)
 *
 * Layout fix: natural page scroll + sticky topbar — NO fixed height wrapper
 * that caused empty gray space inside the flex container.
 *
 * Standard OPPM structure:
 * ┌──────────────────────────────────────────────────────────────────────┐
 * │ PROJECT LEADER:          │ PROJECT NAME:                             │
 * │ PROJECT OBJECTIVE: ...                                               │
 * │ DELIVERABLE OUTPUT: ...                                              │
 * │ START: ___  DEADLINE: ___                              OVERALL: 0%  │
 * ├──────────────────┬─────────────────────────────────────┬─────────────┤
 * │  Sub-Objectives  │ MAJOR TASKS (deadline) │ % │ W1..W10 │ Owners    │
 * │   (1)(2)(3)...  │                         │   │  dots   │  A B C    │
 * ├──────────────────┴────────────────────────────────────┴──────────────┤
 * │ SUMMARY DELIVERABLE  │ FORECAST │ RISK  ║  Team Roster + Metrics    │
 * └──────────────────────────────────────────────────────────────────────┘
 */

import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type {
  OPPMObjective, OPPMSubObjective, OPPMCost, OPPMDeliverable,
  OPPMForecast, OPPMRisk, RagStatus, TaskOwner,
} from '@/types'
import { cn } from '@/lib/utils'
import {
  ArrowLeft, ChevronLeft, ChevronRight, Loader2, Target,
  Check, Plus, Trash2, AlertTriangle, Download, Upload, FileSpreadsheet, X, ScanLine, RotateCcw,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { useChatContext } from '@/hooks/useChatContext'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { transformExcelToFortune } from '@corbe30/fortune-excel'
import defaultTemplateUrl from '@/assets/OPPM Template (1).xlsx?url'

// ──────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────
const VISIBLE_WEEKS       = 10
const SUBOBJ_COUNT        = 6
const SUBOBJ_W            = 22   // px per sub-obj column
const WEEK_W              = 34   // px per week column
const MEMBER_W            = 34   // px per member column
const TASK_NAME_DEFAULT_W = 240
const TASK_NAME_MIN_W     = 120
const OBJ_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
const STATUS_CYCLE = ['empty', 'planned', 'in_progress', 'completed', 'at_risk', 'blocked'] as const

// ──────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────
type TimelineStatus = 'planned' | 'in_progress' | 'completed' | 'at_risk' | 'blocked'
type QualityLevel   = 'good' | 'average' | 'bad'

interface OPPMMember {
  id: string
  user_id: string
  display_name: string | null
  email: string
}
interface OPPMWeek { label: string; start: string }
interface OPPMData {
  project: {
    id: string; title: string; description: string | null
    project_code: string | null; objective_summary: string | null
    deliverable_output: string | null
    start_date: string | null; deadline: string | null; end_date: string | null
    status: string; progress: number; budget: number; planning_hours: number
    lead_id: string | null; lead_name: string
  }
  objectives: OPPMObjective[]
  sub_objectives: OPPMSubObjective[]
  members: OPPMMember[]
  timeline: { id: string; task_id: string; week_start: string; status: TimelineStatus; quality?: QualityLevel | null }[]
  weeks: OPPMWeek[]
  costs: { total_planned: number; total_actual: number; items: OPPMCost[] }
  deliverables: OPPMDeliverable[]
  forecasts: OPPMForecast[]
  risks: OPPMRisk[]
}

// ──────────────────────────────────────────────────────────────
// Dot config
// ──────────────────────────────────────────────────────────────
interface DotCfg { fill: string; stroke: string; label: string }
const DOT_CFG: Record<string, DotCfg> = {
  planned:     { fill: 'transparent', stroke: '#1e40af', label: 'Planned' },
  in_progress: { fill: '#1e40af',     stroke: '#1e40af', label: 'In Progress' },
  completed:   { fill: '#166534',     stroke: '#166534', label: 'Completed' },
  at_risk:     { fill: '#d97706',     stroke: '#d97706', label: 'At Risk' },
  blocked:     { fill: '#dc2626',     stroke: '#dc2626', label: 'Blocked' },
}
const QUALITY_RING: Record<QualityLevel, string> = {
  good: '#166534', average: '#d97706', bad: '#dc2626',
}
const RAG_BG: Record<RagStatus, string> = {
  green: 'bg-green-500', amber: 'bg-amber-400', red: 'bg-red-500',
}

function nextStatus(cur: string | undefined) {
  const i = STATUS_CYCLE.indexOf((cur ?? 'empty') as typeof STATUS_CYCLE[number])
  return STATUS_CYCLE[(i + 1) % STATUS_CYCLE.length]
}

// ──────────────────────────────────────────────────────────────
// StatusDot
// ──────────────────────────────────────────────────────────────
function StatusDot({
  status, quality, onClick, title, size = 12,
}: {
  status?: string
  quality?: QualityLevel | null
  onClick?: () => void
  title?: string
  size?: number
}) {
  const cfg = status && status !== 'empty' ? DOT_CFG[status] : null
  const ring = quality ? QUALITY_RING[quality] : undefined
  return (
    <svg
      width={size} height={size} viewBox="0 0 12 12"
      onClick={onClick}
      className={cn('shrink-0', onClick && 'cursor-pointer hover:scale-125 transition-transform')}
    >
      <title>{title ?? cfg?.label ?? 'Click to set status'}</title>
      {ring && (
        <circle cx="6" cy="6" r="5.5" fill="transparent" stroke={ring} strokeWidth="1.2" />
      )}
      {cfg ? (
        <circle cx="6" cy="6" r="4" fill={cfg.fill} stroke={cfg.stroke} strokeWidth="1.5" />
      ) : (
        <circle cx="6" cy="6" r="4" fill="transparent" stroke="#d1d5db" strokeWidth="1" strokeDasharray="2 2" />
      )}
    </svg>
  )
}

// ──────────────────────────────────────────────────────────────
// InlineEdit
// ──────────────────────────────────────────────────────────────
function InlineEdit({
  value, onSave, placeholder = '—', className: extra, multiline,
}: {
  value: string
  onSave: (v: string) => void
  placeholder?: string
  className?: string
  multiline?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState(value)
  useEffect(() => { setDraft(value) }, [value])

  const commit = useCallback(() => {
    if (draft !== value) onSave(draft)
    setEditing(false)
  }, [draft, value, onSave])

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !multiline) commit()
    if (e.key === 'Escape') { setDraft(value); setEditing(false) }
  }

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(value); setEditing(true) }}
        className={cn(
          'cursor-text rounded px-0.5 hover:bg-yellow-50 border border-transparent hover:border-yellow-300 transition-colors block truncate',
          !value && 'text-gray-300 italic',
          extra,
        )}
        title="Click to edit"
      >
        {value || placeholder}
      </span>
    )
  }

  if (multiline) {
    return (
      <textarea
        autoFocus value={draft} rows={2}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit} onKeyDown={onKey}
        className={cn('bg-transparent border-b border-blue-500 outline-none w-full resize-none text-inherit', extra)}
      />
    )
  }

  return (
    <input
      autoFocus value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={commit} onKeyDown={onKey}
      className={cn('bg-transparent border-b border-blue-500 outline-none w-full text-inherit', extra)}
    />
  )
}

// ──────────────────────────────────────────────────────────────
// RiskLine
// ──────────────────────────────────────────────────────────────
function RiskLine({
  item, onRag, onDesc,
}: {
  item: OPPMRisk
  onRag: (r: RagStatus) => void
  onDesc: (d: string) => void
}) {
  return (
    <div className="flex items-center gap-1.5 py-1 border-b border-gray-100 last:border-0">
      <div className="flex gap-0.5 shrink-0">
        {(['green', 'amber', 'red'] as RagStatus[]).map(r => (
          <button
            key={r} type="button" onClick={() => onRag(r)}
            className={cn(
              'h-3 w-3 rounded-sm transition-all', RAG_BG[r],
              item.rag === r
                ? 'ring-1 ring-offset-1 ring-gray-400 scale-110'
                : 'opacity-30 hover:opacity-70',
            )}
            title={r}
          />
        ))}
      </div>
      <InlineEdit
        value={item.description} onSave={onDesc}
        placeholder="Click to add risk…"
        className="text-[11px] text-gray-700 flex-1"
      />
    </div>
  )
}

// ──────────────────────────────────────────────────────────────
// LegendDot
// ──────────────────────────────────────────────────────────────
function LegendDot({ status, label }: { status: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <StatusDot status={status} size={11} />
      <span className="text-[10px] text-gray-500">{label}</span>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────
// addDays helper
// ──────────────────────────────────────────────────────────────
function addDays(iso: string, n: number): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

// ══════════════════════════════════════════════════════════════
// OPPMView — Main component
// ══════════════════════════════════════════════════════════════
export function OPPMView() {
  const { id }  = useParams<{ id: string }>()
  const qc      = useQueryClient()
  const ws      = useWorkspaceStore(s => s.currentWorkspace)
  const wsPath  = ws ? `/v1/workspaces/${ws.id}` : ''

  const [weekOffset, setWeekOffset] = useState(0)
  const [newObjTitle, setNewObjTitle] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<Record<string, number> | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const scanInputRef = useRef<HTMLInputElement>(null)
  const gridRef     = useRef<HTMLDivElement>(null)

  // OCR / preview state
  const [scanning,    setScanning]    = useState(false)
  const [scanModel,   setScanModel]   = useState('llava')
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [ocrPreview,  setOcrPreview]  = useState<any>(null)
  const [previewSrc,  setPreviewSrc]  = useState<'xlsx' | 'scan'>('xlsx')
  const [ocrSaving,   setOcrSaving]   = useState(false)
  const [ocrError,    setOcrError]    = useState<string | null>(null)
  const [showAddCost, setShowAddCost] = useState(false)
  const [newCost, setNewCost] = useState({
    category: '', planned_amount: 0, actual_amount: 0, description: '',
  })
  const [taskNameW, setTaskNameW] = useState(() => {
    const s = localStorage.getItem('oppm-task-col-w')
    return s ? Math.max(TASK_NAME_MIN_W, +s) : TASK_NAME_DEFAULT_W
  })

  // ── Combined query ──────────────────────────────────────
  const qKey = ['oppm-data', id, ws?.id] as const
  const { data: oppm, isLoading } = useQuery<OPPMData>({
    queryKey: qKey,
    queryFn:  () => api.get<OPPMData>(`${wsPath}/projects/${id}/oppm`),
    enabled:  !!(ws && id),
  })
  useChatContext('project', id, oppm?.project.title)

  // ── Spreadsheet template ─────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetDataRef = useRef<any[] | null>(null)
  const [sheetKey, setSheetKey] = useState(0)
  const [sheetFileName, setSheetFileName] = useState<string | null>(null)
  const [sheetSaving, setSheetSaving] = useState(false)
  const [sheetSaved, setSheetSaved] = useState(false)
  const [autoLoading, setAutoLoading] = useState(false)
  const [forceSystemView, setForceSystemView] = useState(false)
  const sheetRef = useRef<any>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const spreadsheetQKey = ['oppm-spreadsheet', id, ws?.id] as const
  const { data: spreadsheetData, isLoading: ssLoading } = useQuery<{ sheet_data: any[]; file_name: string | null } | null>({
    queryKey: spreadsheetQKey,
    queryFn: async () => {
      const res = await fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}` },
      })
      if (res.status === 404) return null
      if (!res.ok) throw new Error('Failed to load spreadsheet')
      return res.json()
    },
    enabled: !!(ws && id),
    retry: false,
  })

  const hasSheet = !!(sheetDataRef.current && sheetDataRef.current.length > 0)
  const viewMode: 'system' | 'spreadsheet' = (hasSheet && !forceSystemView) ? 'spreadsheet' : 'system'

  // Sync query result into ref (on first load or after invalidation)
  useEffect(() => {
    if (spreadsheetData?.sheet_data) {
      sheetDataRef.current = spreadsheetData.sheet_data
      setSheetFileName(spreadsheetData.file_name ?? null)
      setSheetKey(k => k + 1)
    }
  }, [spreadsheetData])

  // Auto-load default template from bundled XLSX when none exists
  useEffect(() => {
    if (ssLoading || autoLoading || spreadsheetData?.sheet_data || !ws || !id) return
    let cancelled = false
    ;(async () => {
      setAutoLoading(true)
      try {
        const res = await fetch(defaultTemplateUrl)
        if (!res.ok) { setAutoLoading(false); return }
        const blob = await res.blob()
        const file = new File([blob], 'OPPM Template.xlsx', {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        await transformExcelToFortune(
          file,
          (sheets: any[]) => {
            if (cancelled) return
            sheetDataRef.current = sheets
            setSheetFileName('OPPM Template.xlsx')
            setSheetKey(k => k + 1)
            // Persist to backend
            const token = localStorage.getItem('access_token') ?? ''
            fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
              method: 'PUT',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({ sheet_data: sheets, file_name: 'OPPM Template.xlsx' }),
            }).then(() => qc.invalidateQueries({ queryKey: spreadsheetQKey }))
          },
          () => {},
          sheetRef,
        )
      } catch { /* fall back to system view */ }
      if (!cancelled) setAutoLoading(false)
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ssLoading, spreadsheetData, ws, id])

  // Save sheet data to backend (debounce target)
  const saveSheetToBackend = useCallback(async () => {
    if (!ws || !id || !sheetDataRef.current) return
    setSheetSaving(true)
    setSheetSaved(false)
    try {
      await fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}`,
        },
        body: JSON.stringify({ sheet_data: sheetDataRef.current, file_name: sheetFileName }),
      })
      setSheetSaved(true)
      setTimeout(() => setSheetSaved(false), 2000)
    } finally {
      setSheetSaving(false)
    }
  }, [ws, id, wsPath, sheetFileName])

  // ── Derived ─────────────────────────────────────────────
  const allWeeks     = oppm?.weeks ?? []
  const visibleWeeks = allWeeks.slice(weekOffset, weekOffset + VISIBLE_WEEKS)
  const canBack      = weekOffset > 0
  const canFwd       = weekOffset + VISIBLE_WEEKS < allWeeks.length

  const tlMap = useMemo(() => {
    const m: Record<string, Record<string, { status: TimelineStatus; quality?: QualityLevel | null }>> = {}
    for (const e of oppm?.timeline ?? []) {
      if (!m[e.task_id]) m[e.task_id] = {}
      m[e.task_id][e.week_start] = { status: e.status, quality: e.quality }
    }
    return m
  }, [oppm?.timeline])

  const subObjSlots = useMemo<(OPPMSubObjective | null)[]>(() => {
    const arr: (OPPMSubObjective | null)[] = Array.from({ length: SUBOBJ_COUNT }, () => null)
    for (const so of oppm?.sub_objectives ?? []) {
      if (so.position >= 1 && so.position <= SUBOBJ_COUNT) arr[so.position - 1] = so
    }
    return arr
  }, [oppm?.sub_objectives])

  const members    = (oppm?.members ?? []).slice(0, 5)
  const costs      = oppm?.costs?.items ?? []
  const maxCost    = Math.max(...costs.flatMap(c => [c.planned_amount, c.actual_amount]), 1)
  const costDif    = (oppm?.costs?.total_actual ?? 0) - (oppm?.costs?.total_planned ?? 0)
  const todayIso   = format(new Date(), 'yyyy-MM-dd')
  const curWeekIdx = visibleWeeks.findIndex(w => w.start <= todayIso && todayIso < addDays(w.start, 7))
  // total table columns (for full-width spans)
  const totalCols  = SUBOBJ_COUNT + 1 + 1 + visibleWeeks.length + members.length
  const atRiskCnt  = (oppm?.timeline ?? []).filter(e => e.status === 'at_risk' || e.status === 'blocked').length

  const weekRangeLabel = visibleWeeks.length
    ? `${visibleWeeks[0].label} – ${visibleWeeks[visibleWeeks.length - 1].label}`
    : ''

  const initials = (m: OPPMMember) => {
    const n = m.display_name || m.email.split('@')[0]
    return n.includes(' ')
      ? n.split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2)
      : n.slice(0, 2).toUpperCase()
  }

  const taskPct = (taskId: string) => {
    const entries = Object.values(tlMap[taskId] ?? {})
    if (!entries.length) return null
    return Math.round((entries.filter(e => e.status === 'completed').length / entries.length) * 100)
  }

  // ── Invalidate helper ───────────────────────────────────
  const inv = useCallback(() => qc.invalidateQueries({ queryKey: qKey }), [qc, qKey])

  // ── Mutations ────────────────────────────────────────────
  const createObj = useMutation({
    mutationFn: (title: string) =>
      api.post(`${wsPath}/projects/${id}/oppm/objectives`, {
        title, project_id: id, sort_order: (oppm?.objectives?.length ?? 0) + 1,
      }),
    onSuccess: () => { inv(); setNewObjTitle('') },
  })
  const updateObj = useMutation({
    mutationFn: ({ objId, data }: { objId: string; data: Record<string, unknown> }) =>
      api.put(`${wsPath}/oppm/objectives/${objId}`, data),
    onSuccess: inv,
  })
  const deleteObj = useMutation({
    mutationFn: (objId: string) => api.delete(`${wsPath}/oppm/objectives/${objId}`),
    onSuccess: inv,
  })
  const upsertTl = useMutation({
    mutationFn: (d: { task_id: string; week_start: string; status: string }) =>
      api.put(`${wsPath}/projects/${id}/oppm/timeline`, d),
    onSuccess: inv,
  })
  const updateTask = useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: Record<string, unknown> }) =>
      api.put(`${wsPath}/tasks/${taskId}`, data),
    onSuccess: inv,
  })
  const setOwner = useMutation({
    mutationFn: (d: { taskId: string; member_id: string; priority: string }) =>
      api.put(`${wsPath}/projects/${id}/oppm/tasks/${d.taskId}/owners`, {
        member_id: d.member_id, priority: d.priority,
      }),
    onSuccess: inv,
  })
  const removeOwner = useMutation({
    mutationFn: (d: { taskId: string; member_id: string }) =>
      api.delete(`${wsPath}/projects/${id}/oppm/tasks/${d.taskId}/owners/${d.member_id}`),
    onSuccess: inv,
  })
  const setTaskSO = useMutation({
    mutationFn: (d: { taskId: string; sub_objective_ids: string[] }) =>
      api.put(`${wsPath}/projects/${id}/oppm/tasks/${d.taskId}/sub-objectives`, {
        sub_objective_ids: d.sub_objective_ids,
      }),
    onSuccess: inv,
  })
  const createSO = useMutation({
    mutationFn: (d: { position: number; label: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/sub-objectives`, d),
    onSuccess: inv,
  })
  const updateSO = useMutation({
    mutationFn: ({ soId, data }: { soId: string; data: { label?: string } }) =>
      api.put(`${wsPath}/oppm/sub-objectives/${soId}`, data),
    onSuccess: inv,
  })
  const createDeliv = useMutation({
    mutationFn: (d: { item_number: number; description: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/deliverables`, d),
    onSuccess: inv,
  })
  const updateDeliv = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: { description?: string } }) =>
      api.put(`${wsPath}/oppm/deliverables/${itemId}`, data),
    onSuccess: inv,
  })
  const createFcst = useMutation({
    mutationFn: (d: { item_number: number; description: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/forecasts`, d),
    onSuccess: inv,
  })
  const updateFcst = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: { description?: string } }) =>
      api.put(`${wsPath}/oppm/forecasts/${itemId}`, data),
    onSuccess: inv,
  })
  const createRisk = useMutation({
    mutationFn: (d: { item_number: number; description: string; rag?: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/risks`, d),
    onSuccess: inv,
  })
  const updateRisk = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: { description?: string; rag?: string } }) =>
      api.put(`${wsPath}/oppm/risks/${itemId}`, data),
    onSuccess: inv,
  })
  const createCost = useMutation({
    mutationFn: (d: { category: string; planned_amount: number; actual_amount: number; description: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/costs`, { ...d, project_id: id }),
    onSuccess: () => {
      inv()
      setShowAddCost(false)
      setNewCost({ category: '', planned_amount: 0, actual_amount: 0, description: '' })
    },
  })
  const updateCost = useMutation({
    mutationFn: ({ costId, data }: { costId: string; data: Record<string, unknown> }) =>
      api.put(`${wsPath}/oppm/costs/${costId}`, data),
    onSuccess: inv,
  })
  const deleteCost = useMutation({
    mutationFn: (costId: string) => api.delete(`${wsPath}/oppm/costs/${costId}`),
    onSuccess: inv,
  })

  // ── Dot click ────────────────────────────────────────────
  const dotClick = useCallback((taskId: string, weekStart: string) => {
    const cur  = tlMap[taskId]?.[weekStart]?.status ?? 'empty'
    const next = nextStatus(cur)
    upsertTl.mutate({
      task_id: taskId, week_start: weekStart,
      status: next === 'empty' ? 'planned' : next,
    })
  }, [tlMap, upsertTl])

  // ── Column resize ────────────────────────────────────────
  const resizing = useRef(false)
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizing.current = true
    const x0 = e.clientX
    const w0 = taskNameW
    const onMove = (ev: MouseEvent) => {
      if (resizing.current) setTaskNameW(Math.max(TASK_NAME_MIN_W, w0 + ev.clientX - x0))
    }
    const onUp = (ev: MouseEvent) => {
      resizing.current = false
      localStorage.setItem('oppm-task-col-w', String(Math.max(TASK_NAME_MIN_W, w0 + ev.clientX - x0)))
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [taskNameW])

  // ── Template download ─────────────────────────────────────
  const handleGetTemplate = async () => {
    if (!ws || !id) return
    const token = localStorage.getItem('access_token')
    try {
      const res = await fetch(`/api/v1/workspaces/${ws.id}/projects/${id}/oppm/template`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) return
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url
      a.download = `oppm-template-${oppm?.project.title ?? 'project'}.xlsx`
      document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch { /* intentional */ }
  }

  // ── XLSX import — convert to FortuneSheet and save as spreadsheet template ──
  const handleImport = async (file: File) => {
    if (!ws || !id) return
    setImporting(true)
    setImportResult(null)
    setImportError(null)
    try {
      // Client-side XLSX → FortuneSheet JSON conversion
      await transformExcelToFortune(
        file,
        (sheets: any[]) => {
          sheetDataRef.current = sheets
          setSheetFileName(file.name)
          setSheetKey(k => k + 1)
          setForceSystemView(false)
          // Persist to backend
          const token = localStorage.getItem('access_token')
          fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ sheet_data: sheets, file_name: file.name }),
          }).then(res => {
            if (res.ok) {
              qc.invalidateQueries({ queryKey: spreadsheetQKey })
              setImportResult({ template_uploaded: 1 })
            } else {
              setImportError('Failed to save spreadsheet template')
            }
          }).catch(() => setImportError('Network error saving template'))
        },
        (_k: number) => { /* setKey not needed — we manage state ourselves */ },
        sheetRef,
      )
    } catch {
      setImportError('Failed to parse XLSX file')
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Reset to system view ──────────────────────────────────
  const handleResetToSystem = async () => {
    if (!ws || !id) return
    if (!confirm('Remove the uploaded spreadsheet and go back to the system OPPM view?')) return
    const token = localStorage.getItem('access_token')
    await fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    sheetDataRef.current = null
    setSheetFileName(null)
    setForceSystemView(true)
    qc.invalidateQueries({ queryKey: spreadsheetQKey })
  }

  // ── Scan image with Ollama OCR ────────────────────────────────
  const handleScan = async (file: File) => {
    if (!ws || !id) return
    setScanning(true)
    setOcrPreview(null)
    setOcrError(null)
    const token = localStorage.getItem('access_token')
    const form  = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(
        `/api/v1/workspaces/${ws.id}/ai/oppm-extract?model_id=${encodeURIComponent(scanModel)}`,
        { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form },
      )
      const body = await res.json()
      if (!res.ok) {
        setOcrError(body?.detail ?? 'OCR extraction failed')
      } else {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setOcrPreview(body as any)
        setPreviewSrc('scan')
      }
    } catch {
      setOcrError('Network error — please try again')
    } finally {
      setScanning(false)
      if (scanInputRef.current) scanInputRef.current.value = ''
    }
  }

  const handleOcrImport = async () => {
    if (!ws || !id || !ocrPreview) return
    setOcrSaving(true)
    setOcrError(null)
    const token = localStorage.getItem('access_token')
    try {
      const res = await fetch(`/api/v1/workspaces/${ws.id}/projects/${id}/oppm/import-json`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(ocrPreview),
      })
      const body = await res.json()
      if (!res.ok) {
        setOcrError(body?.detail ?? 'Import failed')
      } else {
        setImportResult(body as Record<string, number>)
        setOcrPreview(null)
        inv()
        setTimeout(() => gridRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 400)
      }
    } catch {
      setOcrError('Network error — please try again')
    } finally {
      setOcrSaving(false)
    }
  }

  // ── Export ───────────────────────────────────────────────
  const handleExport = async () => {
    if (!ws || !id) return
    const token = localStorage.getItem('access_token')
    try {
      const res = await fetch(`/api/v1/workspaces/${ws.id}/projects/${id}/oppm/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) return
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url
      a.download = `oppm-${oppm?.project.title ?? 'export'}.xlsx`
      document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch { /* intentional */ }
  }

  // ── Loading state ────────────────────────────────────────
  if (isLoading || !oppm) {
    return (
      <div className="flex items-center justify-center py-24 gap-3">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
        <span className="text-sm text-gray-500">Loading OPPM…</span>
      </div>
    )
  }

  const p    = oppm.project
  const objs = oppm.objectives ?? []

  // ════════════════════════════════════════════════════════
  // RENDER — natural page scroll (NO height: 100dvh wrapper)
  // ════════════════════════════════════════════════════════
  return (
    <div className="font-['Inter',system-ui,sans-serif]">

      {/* ── Sticky top action bar ──────────────────────────── */}
      {/*
        sticky top-0 works correctly here because the page itself
        scrolls (not a fixed-height inner container).
        The Layout's <main className="p-4 sm:p-6"> is the scroll root.
      */}
      <div className="sticky top-0 z-30 bg-white border-b border-gray-200 shadow-sm -mx-4 sm:-mx-6 px-4 sm:px-6">
        <div className="flex flex-wrap items-center gap-2 py-2">
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
            <h1 className="text-sm font-bold text-gray-900 truncate">{p.title}</h1>
          </div>
          {/* Week navigation — system view only */}
          {viewMode === 'system' && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setWeekOffset(o => Math.max(0, o - VISIBLE_WEEKS))}
              disabled={!canBack}
              className="p-1.5 rounded hover:bg-gray-100 text-gray-500 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-[11px] font-semibold text-gray-700 px-1 min-w-[90px] text-center">
              {weekRangeLabel}
            </span>
            <button
              onClick={() => setWeekOffset(o => Math.min(Math.max(0, allWeeks.length - VISIBLE_WEEKS), o + VISIBLE_WEEKS))}
              disabled={!canFwd}
              className="p-1.5 rounded hover:bg-gray-100 text-gray-500 disabled:opacity-30 transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          )}
          {viewMode === 'system' && (
          <>
          <button
            onClick={() => scanInputRef.current?.click()}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 rounded-lg border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-100 shadow-sm transition-colors disabled:opacity-50"
            title="Scan OPPM image with Ollama AI"
          >
            {scanning
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <ScanLine className="h-3.5 w-3.5" />}
            Scan with AI
          </button>
          <input
            ref={scanInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0]
              if (f) handleScan(f)
            }}
          />
          <button
            onClick={handleGetTemplate}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 shadow-sm transition-colors"
            title="Download blank import template"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            Get Template
          </button>
          </>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 shadow-sm transition-colors disabled:opacity-50"
            title="Import data from XLSX"
          >
            {importing
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Upload className="h-3.5 w-3.5" />}
            Import XLSX
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0]
              if (f) handleImport(f)
            }}
          />
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-800 shadow-sm transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download OPPM
          </button>
          {viewMode === 'spreadsheet' && (
            <button
              onClick={handleResetToSystem}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 shadow-sm transition-colors"
              title="Remove uploaded spreadsheet and use system OPPM view"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              System View
            </button>
          )}
          {sheetSaving && (
            <span className="text-[10px] text-gray-400 animate-pulse">Saving…</span>
          )}
          {sheetSaved && !sheetSaving && (
            <span className="text-[10px] text-green-600 flex items-center gap-0.5"><Check className="h-3 w-3" />Saved</span>
          )}
        </div>
      </div>

      {/* ── Import result / error banner ─────────────────── */}
      {importResult && (
        <div className="mt-2 -mx-4 sm:-mx-6 px-4 sm:px-6">
          <div className="flex items-start gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-2.5">
            <Check className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
            <p className="flex-1 text-xs text-green-800">
              <span className="font-semibold">Import complete — </span>
              {Object.entries(importResult)
                .filter(([, v]) => v > 0)
                .map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`)
                .join(', ') || 'no new records'}
            </p>
            <button onClick={() => setImportResult(null)} className="text-green-500 hover:text-green-700">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
      {importError && (
        <div className="mt-2 -mx-4 sm:-mx-6 px-4 sm:px-6">
          <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-2.5">
            <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
            <p className="flex-1 text-xs text-red-800">{importError}</p>
            <button onClick={() => setImportError(null)} className="text-red-400 hover:text-red-600">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* ── OCR Scan model picker (shown next to Scan button) ── */}
      {/* rendered inline in action bar — model input */}

      {/* ── OPPM Form Preview Modal ────────────────────────── */}
      {ocrPreview && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 backdrop-blur-sm overflow-y-auto py-8 px-4">
          <div className="w-full max-w-4xl bg-white shadow-2xl rounded-xl flex flex-col">

            {/* Header */}
            <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-200 bg-[#1E3A5F] rounded-t-xl">
              {previewSrc === 'xlsx'
                ? <FileSpreadsheet className="h-5 w-5 text-white shrink-0" />
                : <ScanLine className="h-5 w-5 text-white shrink-0" />}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold uppercase tracking-widest text-blue-200">
                  {previewSrc === 'xlsx' ? 'XLSX Preview' : 'AI Scan Result'}
                </p>
                <p className="text-sm font-semibold text-white truncate">
                  {(ocrPreview.project_title as string) || 'Review before importing'}
                </p>
              </div>
              <button onClick={() => setOcrPreview(null)} className="text-blue-200 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Model picker — only shown for AI scan */}
            {previewSrc === 'scan' && (
              <div className="px-6 py-2 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
                <span className="text-[11px] text-gray-500 shrink-0">Ollama model:</span>
                <input
                  value={scanModel}
                  onChange={e => setScanModel(e.target.value)}
                  className="flex-1 text-[11px] border border-gray-300 rounded px-2 py-0.5 text-gray-700 font-mono"
                  placeholder="llava"
                />
                <button
                  onClick={() => scanInputRef.current?.click()}
                  disabled={scanning}
                  className="text-[11px] text-violet-600 hover:text-violet-800 font-semibold disabled:opacity-50"
                >
                  {scanning ? 'Scanning…' : 'Re‑scan'}
                </button>
              </div>
            )}

            {/* OPPM form body */}
            {(() => {
              type PrevTask = { name: string; due_date: string | null; sub_obj_positions: number[] }
              type PrevObj  = { title: string; tasks: PrevTask[] }
              type PrevSO   = { position: number; label: string }
              type PrevRisk = { description: string; rag: string }

              const previewObjs = (ocrPreview.objectives    as PrevObj[]  | undefined) ?? []
              const previewSOs  = (ocrPreview.sub_objectives as PrevSO[]  | undefined) ?? []
              const previewDlv  = (ocrPreview.deliverables  as string[]   | undefined) ?? []
              const previewFcst = (ocrPreview.forecasts     as string[]   | undefined) ?? []
              const previewRsks = (ocrPreview.risks         as PrevRisk[] | undefined) ?? []

              const soMap: Record<number, string> = {}
              previewSOs.forEach(s => { soMap[s.position] = s.label })

              const isEmpty = previewObjs.length === 0 && previewSOs.length === 0
                           && previewDlv.length === 0  && previewFcst.length === 0
                           && previewRsks.length === 0

              if (isEmpty) {
                return (
                  <div className="px-6 py-10">
                    <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
                      <p className="text-sm text-amber-700 font-medium">
                        No data found. Make sure the file follows the OPPM template format and delete the sample rows before uploading.
                      </p>
                    </div>
                  </div>
                )
              }

              return (
                <>
                  {/* ── Main OPPM table ── */}
                  <div className="overflow-x-auto border-b border-gray-200">
                    <table className="border-collapse" style={{ tableLayout: 'fixed', minWidth: 640 }}>
                      <colgroup>
                        {Array.from({ length: 6 }).map((_, i) => (
                          <col key={i} style={{ width: 32 }} />
                        ))}
                        <col style={{ minWidth: 240 }} />
                        <col style={{ width: 96 }} />
                      </colgroup>
                      <thead>
                        <tr>
                          {Array.from({ length: 6 }).map((_, i) => (
                            <th
                              key={i}
                              className="border border-gray-400 bg-[#1e3a5f] text-white text-[9px] font-bold p-0.5 text-center align-bottom"
                              style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: 72 }}
                            >
                              {soMap[i + 1] ?? `SO ${i + 1}`}
                            </th>
                          ))}
                          <th className="border border-gray-400 bg-[#1e3a5f] text-white text-[11px] font-bold px-3 py-2 text-left">Task</th>
                          <th className="border border-gray-400 bg-[#1e3a5f] text-white text-[11px] font-bold px-2 py-2 text-center">Due Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewObjs.map((obj, oi) => (
                          <React.Fragment key={oi}>
                            {/* Objective header row */}
                            <tr className="bg-[#1e3a5f]">
                              <td colSpan={8} className="text-white text-[11px] font-bold px-3 py-1.5 border-b border-[#162d4a]">
                                {obj.title}
                              </td>
                            </tr>
                            {/* Task rows */}
                            {obj.tasks.map((task, ti) => (
                              <tr key={ti} className={ti % 2 === 0 ? 'bg-white' : 'bg-blue-50/40'}>
                                {Array.from({ length: 6 }).map((_, si) => (
                                  <td key={si} className="border border-gray-300 text-center" style={{ height: 28 }}>
                                    {task.sub_obj_positions?.includes(si + 1)
                                      ? <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#1e3a5f]" />
                                      : null}
                                  </td>
                                ))}
                                <td className="border border-gray-300 text-[11px] text-gray-800 px-3 py-1">{task.name}</td>
                                <td className="border border-gray-300 text-[11px] text-gray-500 px-2 py-1 text-center">{task.due_date ?? '—'}</td>
                              </tr>
                            ))}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* ── Deliverables / Forecasts / Risks ── */}
                  {(previewDlv.length > 0 || previewFcst.length > 0 || previewRsks.length > 0) && (
                    <div className="grid grid-cols-3 divide-x divide-gray-200 border-b border-gray-200">
                      <div className="px-5 py-4">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-2">Deliverables</p>
                        {previewDlv.length > 0
                          ? <ul className="space-y-0.5">{previewDlv.map((d, i) => <li key={i} className="text-[11px] text-gray-700">• {d}</li>)}</ul>
                          : <p className="text-[11px] text-gray-400 italic">None</p>}
                      </div>
                      <div className="px-5 py-4">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-2">Forecasts</p>
                        {previewFcst.length > 0
                          ? <ul className="space-y-0.5">{previewFcst.map((f, i) => <li key={i} className="text-[11px] text-gray-700">• {f}</li>)}</ul>
                          : <p className="text-[11px] text-gray-400 italic">None</p>}
                      </div>
                      <div className="px-5 py-4">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-2">Risks</p>
                        {previewRsks.length > 0
                          ? <ul className="space-y-0.5">{previewRsks.map((r, i) => (
                              <li key={i} className="flex items-center gap-1.5 text-[11px] text-gray-700">
                                <span className={cn('h-2 w-2 rounded-full shrink-0', RAG_BG[r.rag as 'green'|'amber'|'red'] ?? 'bg-gray-400')} />
                                {r.description}
                              </li>
                            ))}</ul>
                          : <p className="text-[11px] text-gray-400 italic">None</p>}
                      </div>
                    </div>
                  )}
                </>
              )
            })()}

            {/* Error */}
            {ocrError && (
              <div className="px-6 py-3">
                <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2">
                  <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                  <p className="text-xs text-red-800">{ocrError}</p>
                </div>
              </div>
            )}

            {/* Footer */}
            <div className="px-6 py-4 bg-gray-50 flex items-center gap-3 rounded-b-xl">
              <button
                onClick={() => setOcrPreview(null)}
                className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Discard
              </button>
              <button
                onClick={handleOcrImport}
                disabled={ocrSaving}
                className="flex-1 rounded-lg bg-[#1E3A5F] px-4 py-2 text-sm font-semibold text-white hover:bg-blue-900 transition-colors disabled:opacity-50 inline-flex items-center justify-center gap-2"
              >
                {ocrSaving && <Loader2 className="h-4 w-4 animate-spin" />}
                Import this data
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── OPPM document body ──────────────────────────────── */}
      {viewMode === 'spreadsheet' && sheetDataRef.current ? (
        /* ── FortuneSheet spreadsheet view ── */
        <div className="mt-3 bg-white border border-gray-300 rounded-lg overflow-hidden" style={{ height: 'calc(100vh - 160px)', minHeight: 500 }}>
          <Workbook
            key={sheetKey}
            ref={sheetRef}
            data={sheetDataRef.current}
            onChange={(data: any) => {
              sheetDataRef.current = data
            }}
            onOp={() => {
              if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
              saveTimerRef.current = setTimeout(() => saveSheetToBackend(), 2000)
            }}
          />
        </div>
      ) : (
      /* ── System OPPM grid view ── */
      <div className="mt-3 bg-white border border-gray-300 rounded-lg overflow-hidden">

        {/* ══════════════════════════════════════════════════
            SECTION 1 — PROJECT HEADER (classic OPPM top)
            ══════════════════════════════════════════════════ */}

        {/* Row 1: Leader | Project Name */}
        <div className="grid grid-cols-2 border-b border-gray-300">
          <div className="px-3 py-2.5 border-r border-gray-300">
            <p className="text-[9px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
              Project Leader:
            </p>
            <p className="text-sm font-semibold text-gray-900">{p.lead_name}</p>
          </div>
          <div className="px-3 py-2.5">
            <p className="text-[9px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
              Project Name:
            </p>
            <p className="text-sm font-semibold text-gray-900">{p.title}</p>
          </div>
        </div>

        {/* Row 2: Project Objective */}
        <div className="px-3 py-2 border-b border-gray-300">
          <span className="text-[9px] font-bold uppercase tracking-wider text-gray-400">
            Project Objective:{' '}
          </span>
          <span className="text-[11px] text-gray-700">
            {p.description || p.objective_summary || '—'}
          </span>
        </div>

        {/* Row 3: Deliverable Output */}
        <div className="px-3 py-2 border-b border-gray-300">
          <span className="text-[9px] font-bold uppercase tracking-wider text-gray-400">
            Deliverable Output:{' '}
          </span>
          <span className="text-[11px] text-gray-700">
            {oppm.deliverables.filter(d => d.description).map(d => d.description).join(', ') || p.deliverable_output || '—'}
          </span>
        </div>

        {/* Row 4: Dates + Overall % */}
        <div className="flex items-stretch border-b border-gray-300">
          <div className="px-3 py-2 border-r border-gray-300 flex items-center gap-2">
            <span className="text-[9px] font-bold uppercase text-gray-400">Start:</span>
            <span className="text-sm font-semibold text-gray-800">
              {p.start_date ? format(parseISO(p.start_date), 'M/d/yy') : '—'}
            </span>
          </div>
          <div className="px-3 py-2 border-r border-gray-300 flex items-center gap-2 flex-1">
            <span className="text-[9px] font-bold uppercase text-gray-400">Deadline:</span>
            <span className="text-sm font-semibold text-gray-800">
              {p.deadline ? format(parseISO(p.deadline), 'M/d/yy') : '—'}
            </span>
          </div>
          <div className="px-4 py-2 flex items-center justify-end gap-2 min-w-[100px]">
            <div className="text-right">
              <p className={cn('text-2xl font-black leading-none',
                p.progress >= 80 ? 'text-green-700'
                : p.progress >= 50 ? 'text-blue-700'
                : p.progress > 0  ? 'text-amber-600'
                : 'text-gray-300',
              )}>
                {p.progress}%
              </p>
              <p className="text-[8px] font-bold uppercase text-gray-400">Overall</p>
            </div>
          </div>
        </div>

        {/* ══════════════════════════════════════════════════
            SECTION 2 — MAIN OPPM GRID
            Classic column order:
              [Sub-Obj 1-6] [Major Tasks + deadline] [%] [Week cols] [Member cols]

            Horizontal overflow is handled by overflow-x-auto on this wrapper.
            The table uses tableLayout:fixed for column width control.
            ══════════════════════════════════════════════════ */}
        <div ref={gridRef} className="overflow-x-auto">
          <table
            className="border-collapse"
            style={{ tableLayout: 'fixed', minWidth: 'max-content' }}
          >
            <colgroup>
              {Array.from({ length: SUBOBJ_COUNT }).map((_, i) => (
                <col key={i} style={{ width: SUBOBJ_W }} />
              ))}
              <col style={{ width: taskNameW }} />
              <col style={{ width: 38 }} />{/* % column */}
              {visibleWeeks.map(w => <col key={w.start} style={{ width: WEEK_W }} />)}
              {members.map(m => <col key={m.id} style={{ width: MEMBER_W }} />)}
            </colgroup>

            <thead>
              {/* ── Header row 1: navy bar with section labels ── */}
              <tr className="bg-[#1e3a5f] text-white">
                {/* Sub-obj group header */}
                <th
                  colSpan={SUBOBJ_COUNT}
                  className="border-r border-[#162d4a] py-1.5 align-middle text-center"
                >
                  <span className="text-[8px] font-bold uppercase tracking-wider text-blue-300 px-1">
                    Sub-Obj
                  </span>
                </th>
                {/* Task col header with resize handle */}
                <th
                  className="border-r border-[#162d4a] px-2 py-1.5 text-left align-middle"
                  style={{ width: taskNameW }}
                >
                  <div className="flex items-center relative">
                    <span className="text-[8px] font-bold uppercase tracking-wider text-blue-200">
                      Major Tasks
                    </span>
                    <span className="text-[7px] text-blue-300 ml-1">(deadline)</span>
                    <div
                      onMouseDown={onResizeStart}
                      className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-blue-400/60"
                    />
                  </div>
                </th>
                {/* % col header */}
                <th className="border-r border-[#162d4a] text-center py-1.5 align-middle">
                  <span className="text-[8px] font-bold text-blue-300">%</span>
                </th>
                {/* "PROJECT COMPLETED BY →" spanning all week cols */}
                <th
                  colSpan={visibleWeeks.length}
                  className="border-r border-[#162d4a] text-center py-1.5 align-middle"
                >
                  <span className="text-[8px] font-bold uppercase tracking-wider text-blue-200">
                    PROJECT COMPLETED BY →
                  </span>
                </th>
                {/* Owner / Priority spanning all member cols */}
                {members.length > 0 && (
                  <th colSpan={members.length} className="text-center py-1.5 align-middle">
                    <span className="text-[8px] font-bold uppercase tracking-wider text-blue-200">
                      Owner / Priority
                    </span>
                  </th>
                )}
              </tr>

              {/* ── Header row 2: column detail labels ── */}
              <tr className="border-b border-gray-300 bg-gray-50">
                {/* Sub-objective slots — vertical label text */}
                {subObjSlots.map((so, i) => (
                  <th
                    key={i}
                    className="border-r border-gray-200 text-center align-bottom py-1"
                    style={{ height: 60, verticalAlign: 'bottom' }}
                  >
                    <div className="flex flex-col items-center justify-end h-full pb-1">
                      {so ? (
                        <InlineEdit
                          value={so.label}
                          onSave={v => updateSO.mutate({ soId: so.id, data: { label: v } })}
                          placeholder={`S${i + 1}`}
                          className="text-[7px] font-bold text-gray-600 text-center [writing-mode:vertical-rl] [transform:rotate(180deg)] max-h-[48px] overflow-hidden"
                        />
                      ) : (
                        <button
                          onClick={() => createSO.mutate({ position: i + 1, label: `Sub ${i + 1}` })}
                          className="text-[7px] text-gray-300 hover:text-blue-500 [writing-mode:vertical-rl] [transform:rotate(180deg)]"
                          title={`Add sub-objective ${i + 1}`}
                        >
                          +{i + 1}
                        </button>
                      )}
                    </div>
                  </th>
                ))}
                {/* Task name col */}
                <th className="border-r border-gray-300 px-2 py-1.5 text-left bg-gray-100 text-[8px] font-bold uppercase text-gray-500">
                  Major Tasks
                </th>
                {/* % col */}
                <th className="border-r border-gray-200 text-center bg-gray-100 text-[8px] font-bold text-gray-500 py-1.5">
                  %
                </th>
                {/* Week date labels */}
                {visibleWeeks.map((w, wi) => (
                  <th
                    key={w.start}
                    className={cn(
                      'border-r border-gray-200 text-center py-1.5 text-[8px] font-bold',
                      wi === curWeekIdx ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500',
                    )}
                  >
                    {w.label}
                  </th>
                ))}
                {/* Member initials */}
                {members.map(m => (
                  <th
                    key={m.id}
                    className="border-r border-gray-200 text-center bg-gray-100 py-1.5 text-[7px] font-bold text-gray-500"
                    title={m.display_name ?? m.email}
                  >
                    {initials(m)}
                  </th>
                ))}
              </tr>

              {/* ── Header row 3: A/B/C priority sub-labels ── */}
              {members.length > 0 && (
                <tr className="bg-white border-b border-gray-200">
                  <td colSpan={SUBOBJ_COUNT + 1 + 1 + visibleWeeks.length} className="bg-white" />
                  {members.map((_, mi) => (
                    <td
                      key={mi}
                      className="border-r border-gray-200 text-center text-[7px] text-gray-400 font-bold py-0.5 bg-white"
                    >
                      {mi === 0 ? 'A' : mi <= 2 ? 'B' : 'C'}
                    </td>
                  ))}
                </tr>
              )}
            </thead>

            <tbody>
              {objs.map((obj, oi) => {
                const tasks    = obj.tasks ?? []
                const allE     = tasks.flatMap(t => Object.values(tlMap[t.id] ?? {}))
                const objDone  = allE.filter(e => e.status === 'completed').length
                const objTotal = allE.length
                const objPct   = objTotal ? Math.round((objDone / objTotal) * 100) : null
                const objStatus: string | undefined =
                  !allE.length            ? undefined
                  : allE.every(e => e.status === 'completed') ? 'completed'
                  : allE.some(e => e.status === 'blocked')    ? 'blocked'
                  : allE.some(e => e.status === 'at_risk')    ? 'at_risk'
                  : allE.some(e => e.status === 'in_progress')? 'in_progress'
                  : 'planned'

                return (
                  <React.Fragment key={obj.id}>
                    {/* ── Objective header row (navy) ── */}
                    <tr className="bg-[#1e3a5f] border-b border-[#162d4a]">
                      <td colSpan={totalCols} className="py-1 px-2">
                        <div className="flex items-center gap-1.5">
                          <StatusDot status={objStatus} size={10} />
                          <span className="text-[9px] font-black text-blue-300">
                            {OBJ_LETTERS[oi % 26]}.
                          </span>
                          <InlineEdit
                            value={obj.title}
                            onSave={v => updateObj.mutate({ objId: obj.id, data: { title: v } })}
                            className="text-[11px] font-bold text-white flex-1"
                          />
                          {objPct !== null && (
                            <span className="text-[9px] text-blue-300 font-semibold shrink-0">
                              {objPct}%
                            </span>
                          )}
                          <button
                            onClick={() => {
                              if (confirm(`Delete objective "${obj.title}" and all its tasks?`)) {
                                deleteObj.mutate(obj.id)
                              }
                            }}
                            className="text-blue-400 hover:text-red-300 transition-colors shrink-0"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* ── Task rows ── */}
                    {tasks.map((task, ti) => {
                      const soIds  = new Set(task.sub_objective_ids ?? [])
                      const owners = (task.owners ?? []) as TaskOwner[]
                      const ownerMap: Record<string, string> = {}
                      for (const o of owners) ownerMap[o.member_id] = o.priority
                      const pct = taskPct(task.id)

                      return (
                        <tr key={task.id} className="border-b border-gray-100 hover:bg-blue-50/20">
                          {/* Sub-objective toggle dots */}
                          {subObjSlots.map((so, si) => (
                            <td key={si} className="border-r border-gray-100 text-center py-1.5 align-middle">
                              {so ? (
                                <button
                                  type="button"
                                  onClick={() => {
                                    const next = soIds.has(so.id)
                                      ? [...soIds].filter(x => x !== so.id)
                                      : [...soIds, so.id]
                                    setTaskSO.mutate({ taskId: task.id, sub_objective_ids: next })
                                  }}
                                  className="w-2.5 h-2.5 rounded-full border mx-auto block transition-all hover:scale-125"
                                  style={soIds.has(so.id)
                                    ? { background: '#1e3a5f', borderColor: '#1e3a5f' }
                                    : { background: 'transparent', borderColor: '#d1d5db' }
                                  }
                                  title={`${so.label}: ${soIds.has(so.id) ? 'linked' : 'click to link'}`}
                                />
                              ) : (
                                <span className="block w-2.5 h-2.5 mx-auto" />
                              )}
                            </td>
                          ))}

                          {/* Task name (sticky left) */}
                          <td
                            className="border-r border-gray-100 px-1.5 py-1.5 align-middle bg-white"
                            style={{
                              position: 'sticky',
                              left: SUBOBJ_COUNT * SUBOBJ_W,
                              zIndex: 5,
                              boxShadow: '2px 0 4px -1px rgba(0,0,0,0.05)',
                            }}
                          >
                            <div className="flex items-center gap-1 min-w-0">
                              <span className="text-[8px] font-mono text-gray-400 shrink-0">
                                {oi + 1}.{ti + 1}
                              </span>
                              <InlineEdit
                                value={task.title}
                                onSave={v => updateTask.mutate({ taskId: task.id, data: { title: v } })}
                                className="text-[11px] text-gray-800 font-medium flex-1 min-w-0"
                              />
                              {task.due_date && (
                                <span className="text-[8px] text-gray-400 shrink-0">
                                  {format(parseISO(task.due_date), 'M/d')}
                                </span>
                              )}
                            </div>
                          </td>

                          {/* % complete */}
                          <td className="border-r border-gray-100 text-center py-1.5 align-middle">
                            {pct !== null ? (
                              <span className={cn('text-[9px] font-bold',
                                pct === 100 ? 'text-green-700'
                                : pct >= 50  ? 'text-blue-700'
                                : 'text-amber-600',
                              )}>
                                {pct}%
                              </span>
                            ) : (
                              <span className="text-[8px] text-gray-300">—</span>
                            )}
                          </td>

                          {/* Week dot cells */}
                          {visibleWeeks.map((w, wi) => {
                            const e = tlMap[task.id]?.[w.start]
                            return (
                              <td
                                key={w.start}
                                className={cn(
                                  'border-r border-gray-100 text-center py-1.5 align-middle',
                                  wi === curWeekIdx && 'bg-blue-50/50',
                                )}
                              >
                                <StatusDot
                                  status={e?.status}
                                  quality={e?.quality as QualityLevel | undefined}
                                  onClick={() => dotClick(task.id, w.start)}
                                  title={`${task.title} — week of ${w.label}`}
                                  size={12}
                                />
                              </td>
                            )
                          })}

                          {/* Member A/B/C cells */}
                          {members.map((m) => {
                            const cur = ownerMap[m.id]
                            const cycle: (string | undefined)[] = [undefined, 'A', 'B', 'C']
                            return (
                              <td
                                key={m.id}
                                className="border-r border-gray-100 text-center align-middle py-1"
                              >
                                <button
                                  type="button"
                                  onClick={() => {
                                    const next = cycle[(cycle.indexOf(cur) + 1) % cycle.length]
                                    if (next) {
                                      setOwner.mutate({ taskId: task.id, member_id: m.id, priority: next })
                                    } else {
                                      removeOwner.mutate({ taskId: task.id, member_id: m.id })
                                    }
                                  }}
                                  className={cn(
                                    'w-[18px] h-[18px] rounded text-[8px] font-black transition-colors flex items-center justify-center mx-auto',
                                    cur === 'A' ? 'bg-[#1e3a5f] text-white' :
                                    cur === 'B' ? 'bg-blue-500 text-white' :
                                    cur === 'C' ? 'bg-blue-200 text-blue-900' :
                                    'bg-transparent text-gray-200 hover:bg-gray-100 hover:text-gray-400',
                                  )}
                                  title={cur
                                    ? `${m.display_name ?? m.email}: ${cur}`
                                    : `Assign ${m.display_name ?? m.email}`
                                  }
                                >
                                  {cur ?? '·'}
                                </button>
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}

                    {tasks.length === 0 && (
                      <tr>
                        <td
                          colSpan={totalCols}
                          className="px-4 py-1.5 text-[10px] text-gray-300 italic border-b border-gray-100"
                        >
                          No tasks linked — create tasks in Project Detail and link to this objective.
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}

              {/* ── Empty state ── */}
              {objs.length === 0 && (
                <tr>
                  <td colSpan={totalCols} className="py-10 text-center">
                    <Target className="h-8 w-8 mx-auto mb-2 text-gray-200" />
                    <p className="text-sm font-semibold text-gray-400">No objectives yet</p>
                    <p className="text-xs text-gray-300 mt-1">
                      Add your first objective below to start tracking.
                    </p>
                  </td>
                </tr>
              )}

              {/* ── Add objective row ── */}
              <tr className="bg-white border-t border-gray-200">
                <td colSpan={totalCols} className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Plus className="h-3.5 w-3.5 text-gray-300 shrink-0" />
                    <input
                      value={newObjTitle}
                      onChange={e => setNewObjTitle(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && newObjTitle.trim()) {
                          createObj.mutate(newObjTitle.trim())
                        }
                      }}
                      placeholder="Type a new objective and press Enter…"
                      className="flex-1 text-[11px] bg-transparent outline-none text-gray-700 placeholder:text-gray-300"
                    />
                    <button
                      onClick={() => { if (newObjTitle.trim()) createObj.mutate(newObjTitle.trim()) }}
                      disabled={!newObjTitle.trim() || createObj.isPending}
                      className="shrink-0 inline-flex items-center gap-1 rounded-md bg-blue-700 px-2.5 py-1 text-[10px] font-bold text-white hover:bg-blue-800 disabled:opacity-40 transition-colors"
                    >
                      {createObj.isPending
                        ? <Loader2 className="h-3 w-3 animate-spin" />
                        : <><Plus className="h-3 w-3" />Add</>
                      }
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>{/* end grid overflow wrapper */}

        {/* ══════════════════════════════════════════════════
            SECTION 3 — BOTTOM PANEL (classic OPPM X-diagram)
            Left col:  Summary Deliverable / Forecast / Risk
                       (each with vertical "writing-mode" label)
            Right col: Team roster + Cost metrics + Status legend
            ══════════════════════════════════════════════════ */}
        <div className="border-t-2 border-gray-300 grid grid-cols-2 divide-x divide-gray-300">

          {/* ──────────── LEFT: Deliverables / Forecast / Risk ──────────── */}
          <div className="divide-y divide-gray-200">

            {/* Summary Deliverable */}
            <div className="flex min-h-[80px]">
              <div className="shrink-0 w-10 bg-gray-100 border-r border-gray-200 flex items-center justify-center p-1">
                <span className="text-[8px] font-bold uppercase text-gray-500 [writing-mode:vertical-rl] [transform:rotate(180deg)] tracking-widest">
                  Summary Deliverable
                </span>
              </div>
              <div className="flex-1 p-2.5 min-w-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] font-bold uppercase text-gray-400 tracking-wider">
                    Deliverables
                  </span>
                  <button
                    onClick={() => createDeliv.mutate({
                      item_number: oppm.deliverables.length + 1, description: '',
                    })}
                    className="text-[9px] text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-0.5"
                  >
                    <Plus className="h-2.5 w-2.5" />Add
                  </button>
                </div>
                <div className="space-y-0.5">
                  {oppm.deliverables.map(it => (
                    <div key={it.id} className="flex items-baseline gap-1">
                      <span className="text-[9px] text-gray-400 shrink-0 w-3.5">{it.item_number}.</span>
                      <InlineEdit
                        value={it.description}
                        onSave={v => updateDeliv.mutate({ itemId: it.id, data: { description: v } })}
                        placeholder="Click to add deliverable…"
                        className="text-[11px] text-gray-700"
                      />
                    </div>
                  ))}
                  {!oppm.deliverables.length && (
                    <p className="text-[10px] text-gray-300 italic">None yet.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Forecast */}
            <div className="flex min-h-[70px]">
              <div className="shrink-0 w-10 bg-gray-100 border-r border-gray-200 flex items-center justify-center p-1">
                <span className="text-[8px] font-bold uppercase text-gray-500 [writing-mode:vertical-rl] [transform:rotate(180deg)] tracking-widest">
                  Forecast
                </span>
              </div>
              <div className="flex-1 p-2.5 min-w-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] font-bold uppercase text-gray-400 tracking-wider">
                    Forecast
                  </span>
                  <button
                    onClick={() => createFcst.mutate({
                      item_number: oppm.forecasts.length + 1, description: '',
                    })}
                    className="text-[9px] text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-0.5"
                  >
                    <Plus className="h-2.5 w-2.5" />Add
                  </button>
                </div>
                <div className="space-y-0.5">
                  {oppm.forecasts.map(it => (
                    <div key={it.id} className="flex items-baseline gap-1">
                      <span className="text-[9px] text-gray-400 shrink-0 w-3.5">{it.item_number}.</span>
                      <InlineEdit
                        value={it.description}
                        onSave={v => updateFcst.mutate({ itemId: it.id, data: { description: v } })}
                        placeholder="Click to add forecast…"
                        className="text-[11px] text-gray-700"
                      />
                    </div>
                  ))}
                  {!oppm.forecasts.length && (
                    <p className="text-[10px] text-gray-300 italic">None yet.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Risk */}
            <div className="flex min-h-[80px]">
              <div className="shrink-0 w-10 bg-gray-100 border-r border-gray-200 flex items-center justify-center p-1">
                <span className="text-[8px] font-bold uppercase text-gray-500 [writing-mode:vertical-rl] [transform:rotate(180deg)] tracking-widest">
                  Risk
                </span>
              </div>
              <div className="flex-1 p-2.5 min-w-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] font-bold uppercase text-gray-400 tracking-wider">
                    Risk Register
                  </span>
                  <button
                    onClick={() => createRisk.mutate({
                      item_number: oppm.risks.length + 1, description: '', rag: 'green',
                    })}
                    className="text-[9px] text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-0.5"
                  >
                    <Plus className="h-2.5 w-2.5" />Add
                  </button>
                </div>
                {oppm.risks.map(it => (
                  <RiskLine
                    key={it.id} item={it}
                    onRag={r => updateRisk.mutate({ itemId: it.id, data: { rag: r } })}
                    onDesc={d => updateRisk.mutate({ itemId: it.id, data: { description: d } })}
                  />
                ))}
                {!oppm.risks.length && (
                  <p className="text-[10px] text-gray-300 italic">None yet.</p>
                )}
              </div>
            </div>
          </div>{/* end LEFT */}

          {/* ──────────── RIGHT: Team Roster + Costs + Legend ──────────── */}
          <div className="divide-y divide-gray-200">

            {/* Team roster */}
            <div className="p-3">
              <p className="text-[9px] font-bold uppercase text-gray-400 tracking-wider mb-2">
                # People Working on Project
              </p>
              <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[11px]">
                <span className="text-gray-500 font-medium">Project Leader</span>
                <span className="text-gray-800 font-semibold">{p.lead_name}</span>
                {members.map((m, mi) => (
                  <React.Fragment key={m.id}>
                    <span className="text-gray-400">
                      {mi === 0 ? 'A — Primary' : mi <= 2 ? 'B — Helper' : 'C — Support'}
                    </span>
                    <span className="text-gray-700">{m.display_name || m.email.split('@')[0]}</span>
                  </React.Fragment>
                ))}
                {members.length === 0 && (
                  <span className="text-gray-300 italic col-span-2 text-[10px]">
                    No team members added yet.
                  </span>
                )}
              </div>
            </div>

            {/* Cost metrics */}
            <div className="p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[9px] font-bold uppercase text-gray-400 tracking-wider">
                  Cost / Metrics
                </p>
                <button
                  onClick={() => setShowAddCost(v => !v)}
                  className="text-[9px] text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-0.5"
                >
                  <Plus className="h-2.5 w-2.5" />
                  {showAddCost ? 'Cancel' : 'Add'}
                </button>
              </div>

              {!costs.length && !showAddCost && (
                <p className="text-[10px] text-gray-300 italic">No cost items yet.</p>
              )}

              <div className="space-y-2">
                {costs.map((c, ci) => {
                  const over = c.actual_amount > c.planned_amount
                  const p2   = Math.min((c.planned_amount / maxCost) * 100, 100)
                  const a2   = Math.min((c.actual_amount  / maxCost) * 100, 100)
                  return (
                    <div key={c.id} className="group">
                      <div className="flex items-center gap-1 mb-0.5">
                        <span className="text-[9px] text-gray-400 w-4">{ci + 1}.</span>
                        <InlineEdit
                          value={c.category}
                          onSave={v => updateCost.mutate({ costId: c.id, data: { category: v } })}
                          className="text-[10px] font-semibold text-gray-700 flex-1"
                        />
                        <button
                          onClick={() => { if (confirm(`Delete "${c.category}"?`)) deleteCost.mutate(c.id) }}
                          className="opacity-0 group-hover:opacity-100 text-gray-200 hover:text-red-400 transition"
                        >
                          <Trash2 className="h-2.5 w-2.5" />
                        </button>
                      </div>
                      <div className="space-y-0.5 ml-5">
                        {[
                          { label: 'Plan', pct: p2, v: c.planned_amount, cls: 'bg-blue-600' },
                          { label: 'Act',  pct: a2, v: c.actual_amount,  cls: over ? 'bg-red-500' : 'bg-green-600' },
                        ].map(({ label, pct, v, cls }) => (
                          <div key={label} className="flex items-center gap-1">
                            <div className="relative flex-1 h-2.5 bg-gray-100 rounded-sm overflow-hidden border border-gray-200">
                              <div className={cn('h-full transition-all', cls)} style={{ width: `${pct}%` }} />
                              <div className="absolute inset-0 flex items-center justify-end pr-0.5">
                                <span className="text-[7px] font-bold text-white drop-shadow">
                                  {v.toLocaleString()}
                                </span>
                              </div>
                            </div>
                            <span className={cn(
                              'text-[8px] w-8 text-right font-semibold shrink-0',
                              over && label === 'Act' ? 'text-red-600' : 'text-gray-400',
                            )}>
                              {label}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>

              {showAddCost && (
                <div className="mt-2 rounded border border-blue-200 bg-blue-50 p-2 space-y-1.5">
                  <input
                    value={newCost.category}
                    onChange={e => setNewCost(c => ({ ...c, category: e.target.value }))}
                    placeholder="Category (e.g. Labour, Hardware)"
                    className="w-full rounded border border-gray-300 px-2 py-1 text-[11px] outline-none focus:border-blue-500 bg-white"
                  />
                  <div className="grid grid-cols-2 gap-1">
                    <input
                      type="number" value={newCost.planned_amount || ''}
                      onChange={e => setNewCost(c => ({ ...c, planned_amount: parseFloat(e.target.value) || 0 }))}
                      placeholder="Planned"
                      className="rounded border border-gray-300 px-2 py-1 text-[11px] outline-none bg-white text-right"
                    />
                    <input
                      type="number" value={newCost.actual_amount || ''}
                      onChange={e => setNewCost(c => ({ ...c, actual_amount: parseFloat(e.target.value) || 0 }))}
                      placeholder="Actual"
                      className="rounded border border-gray-300 px-2 py-1 text-[11px] outline-none bg-white text-right"
                    />
                  </div>
                  <button
                    onClick={() => { if (newCost.category.trim()) createCost.mutate(newCost) }}
                    className="w-full rounded bg-blue-700 text-white text-[11px] font-bold py-1 hover:bg-blue-800 flex items-center justify-center gap-1"
                  >
                    <Check className="h-3 w-3" />Save Cost Item
                  </button>
                </div>
              )}

              {costs.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100 flex justify-between items-end text-[10px]">
                  <span className="text-gray-500">Total</span>
                  <div className="text-right">
                    <div className="text-blue-700 font-semibold">
                      Plan: {(oppm.costs?.total_planned ?? 0).toLocaleString()}
                    </div>
                    <div className={cn('font-bold', costDif > 0 ? 'text-red-600' : 'text-green-700')}>
                      Act: {(oppm.costs?.total_actual ?? 0).toLocaleString()}
                      {costDif !== 0 && (
                        <span className="ml-1">
                          ({costDif > 0 ? '+' : ''}{costDif.toLocaleString()})
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Status legend */}
            <div className="p-3">
              <p className="text-[9px] font-bold uppercase text-gray-400 tracking-wider mb-1.5">
                Status Legend
              </p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                {Object.entries(DOT_CFG).map(([k, v]) => (
                  <LegendDot key={k} status={k} label={v.label} />
                ))}
              </div>
              {atRiskCnt > 0 && (
                <div className="mt-2 flex items-center gap-1 text-amber-600 text-[10px] font-semibold">
                  <AlertTriangle className="h-3 w-3" />
                  {atRiskCnt} item{atRiskCnt > 1 ? 's' : ''} at risk or blocked
                </div>
              )}
            </div>
          </div>{/* end RIGHT */}
        </div>{/* end bottom grid */}

      </div>
      )}
    </div>
  )
}
