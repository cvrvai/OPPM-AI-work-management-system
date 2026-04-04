/**
 * OPPMView — One Page Project Manager (Fully Editable)
 * Layout redesigned to match the classic Excel OPPM template.
 *
 * Features:
 * - Clickable StatusDots that cycle: empty → planned → in_progress → completed → at_risk → blocked
 * - Inline editing for objective titles and owners
 * - Add/delete objectives
 * - Timeline entries fetched from API (oppm_timeline_entries table)
 * - Cost section with CRUD
 * - Editable deliverables, forecast, risks (saved to project metadata)
 * - Week navigation with current week highlight
 * - Auto-calculated progress per objective and overall
 */

import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import type { Project, OPPMObjective, OPPMTimelineEntry, OPPMCost } from '@/types'
import { cn, formatDate, getStatusColor } from '@/lib/utils'
import {
  ArrowLeft, ChevronLeft, ChevronRight, Loader2, Target,
  Check, Plus, Trash2,
} from 'lucide-react'
import { startOfWeek, addWeeks, format, parseISO, isWithinInterval, endOfWeek } from 'date-fns'
import { useChatContext } from '@/hooks/useChatContext'

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────
const VISIBLE_WEEKS = 8
const OBJ_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
const MIN_OBJECTIVE_ROWS = 6

// Column widths for main table
// [row#] [sub-obj] [major-tasks] [8×week] [owner]
const COL_ROW_NUM  = 30
const COL_SUB_OBJ  = 56
const COL_TASKS    = 340
const COL_WEEK     = 54
const COL_OWNER    = 90
// Total data cols (excluding row#): 1+1+8+1 = 11
// Total cols: 12

// Shared cell class helpers
const RN  = 'border border-slate-300 bg-slate-100 px-1 py-1 text-center text-[10px] font-medium text-slate-500 align-top'
const HD  = 'sticky top-0 z-20 border border-slate-300 bg-slate-200 px-1 py-1 text-center text-[10px] font-semibold text-slate-500'
const CELL = 'border border-slate-300 bg-white align-top'
const LBL  = 'text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-400'

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  planned:     { color: '#3B82F6', bg: 'border-[2px] border-blue-400 bg-blue-50',  label: 'Planned' },
  in_progress: { color: '#3B82F6', bg: 'bg-blue-500',     label: 'In Progress' },
  completed:   { color: '#22C55E', bg: 'bg-emerald-500',  label: 'Completed' },
  at_risk:     { color: '#F59E0B', bg: 'bg-amber-400',    label: 'At Risk' },
  blocked:     { color: '#EF4444', bg: 'bg-red-500',      label: 'Blocked' },
}

const STATUS_CYCLE = ['empty', 'planned', 'in_progress', 'completed', 'at_risk', 'blocked'] as const
type TimelineStatus = 'planned' | 'in_progress' | 'completed' | 'at_risk' | 'blocked'

function nextStatus(current: string | undefined): string {
  const idx = STATUS_CYCLE.indexOf((current || 'empty') as typeof STATUS_CYCLE[number])
  return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length]
}

// ─────────────────────────────────────────────────────────────
// Metadata types
// ─────────────────────────────────────────────────────────────
interface RiskItem { text: string; rag: 'green' | 'amber' | 'red' }
interface OPPMMetadata {
  deliverable_output?: string
  summary_deliverables?: string[]
  forecast?: string | string[]
  risks?: RiskItem[] | string[]
}
interface NormalizedMeta {
  deliverable_output: string
  summary_deliverables: string[]
  forecast: string
  risks: RiskItem[]
}

// ─────────────────────────────────────────────────────────────
// StatusDot
// ─────────────────────────────────────────────────────────────
function StatusDot({ status, onClick }: { status?: string; onClick?: () => void }) {
  const cfg = status && status !== 'empty' ? STATUS_CONFIG[status] : null
  return (
    <div
      onClick={onClick}
      title={cfg?.label ?? 'Click to set status'}
      className={cn(
        'w-3.5 h-3.5 rounded-full mx-auto transition-all duration-150 shrink-0',
        onClick && 'cursor-pointer hover:scale-125',
        cfg ? cfg.bg : 'border-[1.5px] border-gray-300 bg-transparent',
      )}
    />
  )
}

// ─────────────────────────────────────────────────────────────
// OwnerSelect
// ─────────────────────────────────────────────────────────────
function OwnerSelect({
  value, members, onChange,
}: {
  value: string
  members: { id: string; display_name: string | null; email: string }[]
  onChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = members.find(m => m.id === value)
  const label = selected ? (selected.display_name || selected.email.split('@')[0]) : '—'
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])
  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-center gap-0.5 text-[10px] text-gray-600 hover:text-gray-900"
      >
        <span className="truncate max-w-[72px]">{label}</span>
        <svg className="h-2.5 w-2.5 shrink-0 text-gray-400" viewBox="0 0 12 12" fill="none">
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-0.5 z-50 min-w-[130px] rounded-lg border border-gray-200 bg-white shadow-lg py-1">
          <button type="button" className="w-full px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-50 text-left" onClick={() => { onChange(''); setOpen(false) }}>— Unassign</button>
          {members.map(m => (
            <button key={m.id} type="button" className={cn('w-full px-3 py-1.5 text-xs text-left hover:bg-blue-50 hover:text-blue-700', m.id === value ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700')} onClick={() => { onChange(m.id); setOpen(false) }}>
              {m.display_name || m.email.split('@')[0]}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// InlineEdit
// ─────────────────────────────────────────────────────────────
function InlineEdit({ value, onSave, placeholder = 'Click to edit…', className: extraClass }: {
  value: string; onSave: (v: string) => void; placeholder?: string; className?: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { if (editing) ref.current?.focus() }, [editing])
  useEffect(() => { setDraft(value) }, [value])
  if (!editing) {
    return (
      <span onClick={() => { setDraft(value); setEditing(true) }} className={cn('cursor-text rounded px-0.5 hover:bg-amber-50 border border-transparent hover:border-amber-200 transition-colors', !value && 'text-gray-400 italic', extraClass)} title="Click to edit">
        {value || placeholder}
      </span>
    )
  }
  return (
    <input ref={ref} value={draft} onChange={e => setDraft(e.target.value)}
      onBlur={() => { if (draft !== value) onSave(draft); setEditing(false) }}
      onKeyDown={e => { if (e.key === 'Enter') { if (draft !== value) onSave(draft); setEditing(false) } if (e.key === 'Escape') { setDraft(value); setEditing(false) } }}
      className={cn('bg-transparent border-b-[1.5px] border-blue-500 outline-none w-full text-inherit', extraClass)}
    />
  )
}

// ─────────────────────────────────────────────────────────────
// EditableList
// ─────────────────────────────────────────────────────────────
function EditableList({ items, onSave }: { items: string[]; onSave: (items: string[]) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([])
  const startEdit = () => { setDraft([...items]); setEditing(true) }
  if (editing) {
    return (
      <div className="space-y-1">
        {draft.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-400 w-4 shrink-0">{i + 1}.</span>
            <input value={item} onChange={e => { const n = [...draft]; n[i] = e.target.value; setDraft(n) }} className="flex-1 text-xs border border-blue-400 rounded px-1.5 py-0.5 outline-none focus:border-blue-500" />
          </div>
        ))}
        <div className="flex gap-2 mt-1.5">
          <button onClick={() => { onSave(draft); setEditing(false) }} className="text-[10px] bg-blue-600 text-white rounded px-2 py-0.5 font-medium hover:bg-blue-700">Save</button>
          <button onClick={() => setEditing(false)} className="text-[10px] text-gray-500 hover:text-gray-700">Cancel</button>
        </div>
      </div>
    )
  }
  return (
    <div className="cursor-pointer group" onClick={startEdit}>
      {items.map((item, i) => (
        <div key={i} className="text-xs leading-5 hover:bg-amber-50/60 rounded px-0.5">
          <span className="text-gray-400 mr-1">{i + 1}.</span>
          <span className="text-gray-700">{item || <em className="not-italic text-gray-300">—</em>}</span>
        </div>
      ))}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">✎ click to edit</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// RiskEditor
// ─────────────────────────────────────────────────────────────
const RAG_COLORS = {
  green: { dot: 'bg-emerald-500', ring: 'ring-emerald-300' },
  amber: { dot: 'bg-amber-500',   ring: 'ring-amber-300' },
  red:   { dot: 'bg-red-500',     ring: 'ring-red-300' },
} as const

function RiskEditor({ items, onSave }: { items: RiskItem[]; onSave: (items: RiskItem[]) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<RiskItem[]>([])
  const startEdit = () => { setDraft(items.map(it => ({ ...it }))); setEditing(true) }
  if (editing) {
    return (
      <div className="space-y-1.5">
        {draft.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-400 w-4 shrink-0">{i + 1}.</span>
            {(['green', 'amber', 'red'] as const).map(rag => (
              <button key={rag} type="button" onClick={() => { const n = [...draft]; n[i] = { ...n[i], rag }; setDraft(n) }}
                className={cn('h-3.5 w-3.5 rounded-full shrink-0', RAG_COLORS[rag].dot, item.rag === rag ? `ring-2 ${RAG_COLORS[rag].ring} scale-110` : 'opacity-40 hover:opacity-70')} />
            ))}
            <input value={item.text} onChange={e => { const n = [...draft]; n[i] = { ...n[i], text: e.target.value }; setDraft(n) }} className="flex-1 text-xs border border-blue-400 rounded px-1.5 py-0.5 outline-none focus:border-blue-500" />
          </div>
        ))}
        <div className="flex gap-2 mt-1.5">
          <button onClick={() => { onSave(draft); setEditing(false) }} className="text-[10px] bg-blue-600 text-white rounded px-2 py-0.5 font-medium hover:bg-blue-700">Save</button>
          <button onClick={() => setEditing(false)} className="text-[10px] text-gray-500 hover:text-gray-700">Cancel</button>
        </div>
      </div>
    )
  }
  return (
    <div className="cursor-pointer group" onClick={startEdit}>
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs leading-5 hover:bg-amber-50/60 rounded px-0.5">
          <span className="text-gray-400 shrink-0">{i + 1}.</span>
          <span className={cn('h-2.5 w-2.5 rounded-full shrink-0', RAG_COLORS[item.rag].dot)} />
          <span className="text-gray-700">{item.text || <em className="not-italic text-gray-300">—</em>}</span>
        </div>
      ))}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">✎ click to edit</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// InlineTextarea
// ─────────────────────────────────────────────────────────────
function InlineTextarea({ value, onSave, emptyMessage = 'Click to add notes...' }: {
  value: string; onSave: (value: string) => void; emptyMessage?: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const startEdit = () => { setDraft(value); setEditing(true) }
  if (editing) {
    return (
      <div className="space-y-1.5">
        <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={4} className="w-full text-xs border border-blue-400 rounded px-2 py-1.5 outline-none focus:border-blue-500 resize-none" autoFocus />
        <div className="flex gap-2">
          <button onClick={() => { onSave(draft); setEditing(false) }} className="text-[10px] bg-blue-600 text-white rounded px-2 py-0.5 font-medium hover:bg-blue-700">Save</button>
          <button onClick={() => setEditing(false)} className="text-[10px] text-gray-500 hover:text-gray-700">Cancel</button>
        </div>
      </div>
    )
  }
  return (
    <div className="cursor-pointer group" onClick={startEdit}>
      {value ? <p className="text-xs leading-5 text-gray-700 whitespace-pre-wrap">{value}</p> : <p className="text-xs text-gray-300 italic">{emptyMessage}</p>}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">✎ click to edit</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// CostRow
// ─────────────────────────────────────────────────────────────
function CostRow({ cost, maxAmount, onUpdate, onDelete }: {
  cost: OPPMCost; maxAmount: number; onUpdate: (data: Partial<OPPMCost>) => void; onDelete: () => void
}) {
  const safeMax = maxAmount || 1
  const plannedPct = Math.min((cost.planned_amount / safeMax) * 100, 100)
  const actualPct  = Math.min((cost.actual_amount  / safeMax) * 100, 100)
  const overBudget = cost.actual_amount > cost.planned_amount
  return (
    <tr className="hover:bg-gray-50/60">
      <td className="border-b border-gray-200 px-2 py-2 align-middle w-[22%]">
        <InlineEdit value={cost.category} onSave={v => onUpdate({ category: v })} className="text-[11px] font-medium text-gray-700" />
      </td>
      <td className="border-b border-gray-200 px-3 py-1.5 align-middle" style={{ width: '50%' }}>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-400 w-10 shrink-0 font-medium">Planned</span>
            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden border border-gray-200">
              <div className="h-full bg-blue-400 rounded-sm transition-all duration-300" style={{ width: `${plannedPct}%` }} />
            </div>
            <InlineEdit value={String(cost.planned_amount)} onSave={v => onUpdate({ planned_amount: parseFloat(v) || 0 })} className="text-[10px] text-gray-600 w-14 text-right font-mono" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-400 w-10 shrink-0 font-medium">Actual</span>
            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden border border-gray-200">
              <div className={cn('h-full rounded-sm transition-all duration-300', overBudget ? 'bg-red-400' : 'bg-emerald-400')} style={{ width: `${actualPct}%` }} />
            </div>
            <InlineEdit value={String(cost.actual_amount)} onSave={v => onUpdate({ actual_amount: parseFloat(v) || 0 })} className={cn('text-[10px] w-14 text-right font-mono', overBudget ? 'text-red-600 font-bold' : 'text-emerald-600')} />
          </div>
        </div>
      </td>
      <td className="border-b border-gray-200 px-2 py-2 align-middle">
        <InlineEdit value={cost.description} onSave={v => onUpdate({ description: v })} placeholder="—" className="text-[11px] text-gray-500" />
      </td>
      <td className="border-b border-gray-200 px-1 py-2 text-center align-middle w-7">
        <button onClick={onDelete} className="text-gray-300 hover:text-red-500 transition-colors" title="Delete"><Trash2 className="h-3 w-3" /></button>
      </td>
    </tr>
  )
}

// ═════════════════════════════════════════════════════════════
// Main OPPMView Component
// ═════════════════════════════════════════════════════════════
export function OPPMView() {
  const { id } = useParams<{ id: string }>()
  const [weekOffset, setWeekOffset] = useState(0)
  const [newObjTitle, setNewObjTitle] = useState('')
  const [showAddCost, setShowAddCost] = useState(false)
  const [newCost, setNewCost] = useState({ category: '', planned_amount: 0, actual_amount: 0, description: '' })

  const user = useAuthStore(s => s.user)
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore(s => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  // ── Queries ────────────────────────────────────────────────
  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn:  () => api.get<Project>(`${wsPath}/projects/${id}`),
    enabled:  !!ws,
  })
  const { data: wsMembers = [] } = useQuery<{ id: string; user_id: string; display_name: string | null; email: string }[]>({
    queryKey: ['ws-members', ws?.id],
    queryFn:  () => api.get(`${wsPath}/members`),
    enabled:  !!ws,
  })
  useChatContext('project', id, project?.title)
  const { data: objectives, isLoading: loadingObjectives } = useQuery({
    queryKey: ['oppm-objectives', id, ws?.id],
    queryFn:  () => api.get<OPPMObjective[]>(`${wsPath}/projects/${id}/oppm/objectives`),
    enabled:  !!ws,
  })
  const { data: timelineEntries } = useQuery({
    queryKey: ['oppm-timeline', id, ws?.id],
    queryFn:  () => api.get<OPPMTimelineEntry[]>(`${wsPath}/projects/${id}/oppm/timeline`),
    enabled:  !!ws,
  })
  const { data: costData } = useQuery({
    queryKey: ['oppm-costs', id, ws?.id],
    queryFn:  () => api.get<{ total_planned: number; total_actual: number; items: OPPMCost[] }>(`${wsPath}/projects/${id}/oppm/costs`),
    enabled:  !!ws,
  })

  // ── Mutations ──────────────────────────────────────────────
  const createObjective = useMutation({
    mutationFn: (title: string) => api.post(`${wsPath}/projects/${id}/oppm/objectives`, { title, project_id: id, sort_order: (objectives?.length ?? 0) + 1 }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] }); setNewObjTitle('') },
  })
  const updateObjective = useMutation({
    mutationFn: ({ objId, data }: { objId: string; data: Record<string, unknown> }) => api.put(`${wsPath}/oppm/objectives/${objId}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] }),
  })
  const deleteObjective = useMutation({
    mutationFn: (objId: string) => api.delete(`${wsPath}/oppm/objectives/${objId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] }); queryClient.invalidateQueries({ queryKey: ['oppm-timeline', id] }) },
  })
  const upsertTimeline = useMutation({
    mutationFn: (data: { objective_id: string; week_start: string; status: string; notes?: string }) => api.put(`${wsPath}/projects/${id}/oppm/timeline`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-timeline', id] }),
  })
  const createCostMut = useMutation({
    mutationFn: (data: { category: string; planned_amount: number; actual_amount: number; description: string }) => api.post(`${wsPath}/projects/${id}/oppm/costs`, { ...data, project_id: id }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] }); setShowAddCost(false); setNewCost({ category: '', planned_amount: 0, actual_amount: 0, description: '' }) },
  })
  const updateCostMut = useMutation({
    mutationFn: ({ costId, data }: { costId: string; data: Record<string, unknown> }) => api.put(`${wsPath}/oppm/costs/${costId}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] }),
  })
  const deleteCostMut = useMutation({
    mutationFn: (costId: string) => api.delete(`${wsPath}/oppm/costs/${costId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] }),
  })
  const updateMeta = useMutation({
    mutationFn: (patch: OPPMMetadata) => api.put(`${wsPath}/projects/${id}`, { metadata: { ...meta, ...patch } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', id] }),
  })

  // ── Computed ───────────────────────────────────────────────
  const projectStart = useMemo(
    () => startOfWeek(parseISO(project?.start_date || project?.created_at || new Date().toISOString()), { weekStartsOn: 1 }),
    [project?.start_date, project?.created_at],
  )
  const weeks = useMemo(
    () => Array.from({ length: VISIBLE_WEEKS }, (_, i) => {
      const ws2 = addWeeks(projectStart, weekOffset + i)
      return { start: ws2, end: endOfWeek(ws2, { weekStartsOn: 1 }), label: format(ws2, 'MMM d'), weekNum: weekOffset + i + 1, isoDate: format(ws2, 'yyyy-MM-dd') }
    }),
    [weekOffset, projectStart],
  )

  const rawMeta = (project?.metadata as OPPMMetadata) ?? {}
  const normalizedRisks: RiskItem[] = rawMeta.risks?.length
    ? (rawMeta.risks as (string | RiskItem)[]).map(it => typeof it === 'string' ? { text: it, rag: 'green' as const } : it)
    : [{ text: '', rag: 'green' }, { text: '', rag: 'green' }, { text: '', rag: 'green' }, { text: '', rag: 'green' }]

  const normalizedForecast = typeof rawMeta.forecast === 'string'
    ? rawMeta.forecast
    : Array.isArray(rawMeta.forecast) ? rawMeta.forecast.filter(Boolean).join('\n') : ''

  const meta: NormalizedMeta = {
    deliverable_output:   rawMeta.deliverable_output ?? '',
    summary_deliverables: rawMeta.summary_deliverables?.length ? rawMeta.summary_deliverables : ['', '', '', ''],
    forecast:             normalizedForecast,
    risks:                normalizedRisks,
  }

  const timelineMap = useMemo(() => {
    const map: Record<string, Record<string, TimelineStatus>> = {}
    if (!timelineEntries) return map
    for (const entry of timelineEntries) {
      if (!map[entry.objective_id]) map[entry.objective_id] = {}
      map[entry.objective_id][entry.week_start] = entry.status
    }
    return map
  }, [timelineEntries])

  const calcProgress = useCallback((objId: string): number => {
    const all = Object.values(timelineMap[objId] ?? {})
    if (!all.length) return 0
    return Math.round((all.filter(s => s === 'completed').length / all.length) * 100)
  }, [timelineMap])

  const overallProgress = useMemo(() => {
    const objs2 = objectives ?? []
    if (!objs2.length) return 0
    let total = 0, completed = 0
    for (const obj of objs2) {
      const entries = Object.values(timelineMap[obj.id] ?? {})
      total += entries.length
      completed += entries.filter(s => s === 'completed').length
    }
    return total === 0 ? 0 : Math.round((completed / total) * 100)
  }, [objectives, timelineMap])

  const handleDotClickFull = useCallback((objectiveId: string, weekIsoDate: string) => {
    const current = timelineMap[objectiveId]?.[weekIsoDate] || 'empty'
    const next = nextStatus(current)
    upsertTimeline.mutate({ objective_id: objectiveId, week_start: weekIsoDate, status: next === 'empty' ? 'planned' : next })
  }, [timelineMap, upsertTimeline])

  const today = new Date()
  const currentWeekIdx = weeks.findIndex(w => isWithinInterval(today, { start: w.start, end: w.end }))
  const leaderName = user?.full_name ?? user?.user_metadata?.full_name ?? user?.email?.split('@')[0] ?? 'Project Leader'
  const totalTaskCount = useMemo(() => (objectives ?? []).reduce((s, o) => s + (o.tasks?.length ?? 0), 0), [objectives])
  const atRiskCount = useMemo(() => (timelineEntries ?? []).filter(e => e.status === 'at_risk').length, [timelineEntries])
  const blockedCount = useMemo(() => (timelineEntries ?? []).filter(e => e.status === 'blocked').length, [timelineEntries])
  const visibleWindowLabel = useMemo(() => `${format(weeks[0].start, 'MMM d')} – ${format(weeks[weeks.length - 1].end, 'MMM d, yyyy')}`, [weeks])
  const maxCostAmount = useMemo(() => Math.max(...(costData?.items ?? []).flatMap(c => [c.planned_amount, c.actual_amount]), 1), [costData])

  if (loadingProject) return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
  if (!project) return <p className="text-sm text-gray-500 py-12 text-center">Project not found</p>

  const p = project
  const objs = objectives ?? []
  const costs = costData?.items ?? []
  const deliverableCount = meta.summary_deliverables.filter(s => s.trim()).length
  const recordedRiskCount = meta.risks.filter(r => r.text.trim()).length
  const costVariance = (costData?.total_actual ?? 0) - (costData?.total_planned ?? 0)
  const visibleObjRows = Math.max(objs.length, MIN_OBJECTIVE_ROWS)

  // Dynamic row numbers
  let rowNum = 0
  const nextRow = () => ++rowNum

  // Column letter helpers for header row  
  // Cols: [row#] A(sub-obj) B(tasks) C..J(8weeks) K(owner) = 12 cols
  const weekColLetters = Array.from({ length: VISIBLE_WEEKS }, (_, i) => String.fromCharCode(67 + i)) // C-J

  // ── Render ────────────────────────────────────────────────
  return (
    <div className="space-y-3">
      {/* ── Top navigation bar ─────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
        <Link to={`/projects/${id}`} className="rounded-lg border border-slate-300 bg-white p-2 text-slate-500 hover:bg-slate-50 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">OPPM Spreadsheet View</p>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-lg font-semibold text-slate-900">{p.title}</h1>
            <span className={cn('rounded-md px-2 py-0.5 text-[10px] font-semibold capitalize', getStatusColor(p.status))}>{p.status.replace('_', ' ')}</span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setWeekOffset(o => o - 1)} className="rounded-lg border border-slate-300 bg-white p-2 text-slate-500 hover:bg-slate-50"><ChevronLeft className="h-4 w-4" /></button>
          <div className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Visible Window</p>
            <p className="text-xs font-medium text-slate-700">{visibleWindowLabel}</p>
          </div>
          <button onClick={() => setWeekOffset(o => o + 1)} className="rounded-lg border border-slate-300 bg-white p-2 text-slate-500 hover:bg-slate-50"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>

      {/* ── Spreadsheet shell ───────────────────────────────── */}
      <div className="overflow-x-auto rounded-xl border border-slate-300 bg-white shadow-sm">
        {/* Formula bar */}
        <div className="border-b border-slate-300 bg-slate-50 px-3 py-1.5" style={{ minWidth: `${COL_ROW_NUM + COL_SUB_OBJ + COL_TASKS + VISIBLE_WEEKS * COL_WEEK + COL_OWNER + 260 + 16}px` }}>
          <div className="grid items-center gap-2" style={{ gridTemplateColumns: '72px 1fr' }}>
            <div className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">A1</div>
            <div className="flex items-center gap-2 rounded border border-slate-300 bg-white px-3 py-1 text-[11px] text-slate-500">
              <span className="font-semibold text-slate-400">fx</span>
              <span className="truncate">{p.title} — One Page Project Manager</span>
            </div>
          </div>
        </div>

        {/* Table area */}
        <div className="flex items-start gap-0 bg-slate-100 p-2">
          {/* ── Main OPPM table ─────────────────────────────── */}
          <table className="border-collapse table-fixed bg-white text-[11px]" style={{ width: `${COL_ROW_NUM + COL_SUB_OBJ + COL_TASKS + VISIBLE_WEEKS * COL_WEEK + COL_OWNER}px` }}>
            <colgroup>
              <col style={{ width: `${COL_ROW_NUM}px` }} />
              <col style={{ width: `${COL_SUB_OBJ}px` }} />
              <col style={{ width: `${COL_TASKS}px` }} />
              {Array.from({ length: VISIBLE_WEEKS }).map((_, i) => <col key={i} style={{ width: `${COL_WEEK}px` }} />)}
              <col style={{ width: `${COL_OWNER}px` }} />
            </colgroup>

            {/* Column letter headers */}
            <thead>
              <tr>
                <th className={HD} />
                <th className={HD}>A</th>
                <th className={HD}>B</th>
                {weekColLetters.map(l => <th key={l} className={HD}>{l}</th>)}
                <th className={HD}>K</th>
              </tr>
            </thead>

            <tbody>
              {/* ── Row 1: Project Leader | Project Name ────── */}
              {(() => { rowNum = 1; return null })()}
              <tr>
                <td className={RN}>1</td>
                <td colSpan={2} className={cn(CELL, 'px-3 py-2')}>
                  <p className={LBL}>Project Leader:</p>
                  <p className="mt-0.5 text-sm font-bold text-slate-900 leading-5">{leaderName}</p>
                </td>
                <td colSpan={VISIBLE_WEEKS + 1} className={cn(CELL, 'px-3 py-2')}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className={LBL}>Project Name:</p>
                      <p className="mt-0.5 text-sm font-bold text-slate-900 leading-5 truncate">{p.title}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="text-right">
                        <p className={LBL}>Overall</p>
                        <p className={cn('text-xl font-black leading-5 mt-0.5',
                          overallProgress >= 80 ? 'text-emerald-600' : overallProgress >= 50 ? 'text-blue-600' : overallProgress > 0 ? 'text-amber-600' : 'text-slate-300'
                        )}>{overallProgress}%</p>
                      </div>
                      <span className={cn('rounded px-2 py-0.5 text-[10px] font-semibold capitalize shrink-0', getStatusColor(p.status))}>{p.status.replace('_', ' ')}</span>
                    </div>
                  </div>
                </td>
              </tr>

              {/* ── Row 2: Project Objective | Deadline ─────── */}
              <tr>
                <td className={RN}>2</td>
                <td colSpan={2} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <p className={LBL}>Project Objective:</p>
                  <p className="mt-0.5 text-xs leading-5 text-slate-700">{p.description || p.objective_summary || '—'}</p>
                </td>
                <td colSpan={4} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <p className={LBL}>Deliverable Output:</p>
                  <div className="mt-0.5">
                    <InlineTextarea value={meta.deliverable_output} onSave={v => updateMeta.mutate({ deliverable_output: v })} emptyMessage="Click to add deliverable output…" />
                  </div>
                </td>
                <td colSpan={3} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <div className="space-y-1.5">
                    <div>
                      <p className={LBL}>Start Date:</p>
                      <p className="mt-0.5 text-xs font-semibold text-slate-900">{p.start_date ? formatDate(p.start_date) : '—'}</p>
                    </div>
                    <div>
                      <p className={LBL}>Deadline:</p>
                      <p className="mt-0.5 text-xs font-semibold text-slate-900">{p.deadline ? formatDate(p.deadline) : '—'}</p>
                    </div>
                  </div>
                </td>
                <td colSpan={2} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <p className={LBL}>Project Completed By:</p>
                  <p className="mt-0.5 text-xs font-semibold text-slate-900">{p.deadline ? formatDate(p.deadline) : 'Not set'}</p>
                </td>
              </tr>

              {/* ── Row 3: Stats summary ─────────────────────── */}
              <tr>
                <td className={RN}>3</td>
                {[
                  { label: 'Objectives',    val: objs.length },
                  { label: 'Linked Tasks',  val: totalTaskCount },
                  { label: 'Deliverables',  val: deliverableCount },
                  { label: 'Risks',         val: recordedRiskCount },
                  { label: '⚠ Attention',   val: atRiskCount + blockedCount },
                ].map((stat, i) => (
                  <td key={i} colSpan={i < 4 ? 2 : VISIBLE_WEEKS - 6} className={cn(CELL, 'px-2 py-1.5 text-center')}>
                    <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">{stat.label}</p>
                    <p className={cn('text-base font-black', i === 4 && stat.val > 0 ? 'text-amber-600' : 'text-slate-900')}>{stat.val}</p>
                  </td>
                ))}
                <td colSpan={3} className={cn(CELL, 'px-2 py-1.5 text-center')}>
                  <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">Cost Variance</p>
                  <p className={cn('text-base font-black', costVariance > 0 ? 'text-red-600' : costVariance < 0 ? 'text-emerald-600' : 'text-slate-900')}>
                    {costVariance === 0 ? '0' : `${costVariance > 0 ? '+' : ''}${costVariance.toLocaleString()}`}
                  </p>
                </td>
              </tr>

              {/* ── Row 4: "Execution Plan" section header ───── */}
              <tr>
                <td className={RN}>4</td>
                <td colSpan={VISIBLE_WEEKS + 2} className="border border-slate-300 bg-slate-800 px-3 py-1.5">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white">Execution Plan</p>
                    <p className="text-[10px] text-slate-400">{visibleWindowLabel}</p>
                  </div>
                </td>
              </tr>

              {/* ── Row 5: Column headers ─────────────────────── */}
              <tr>
                <td className={RN}>5</td>
                <td className="border border-slate-300 bg-slate-100 px-2 py-2 text-center text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Sub<br />Obj
                </td>
                <td className="border border-slate-300 bg-slate-100 px-3 py-2 text-left text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Major Tasks&nbsp;&nbsp;&nbsp;(Deadline)
                </td>
                {weeks.map((week, i) => (
                  <td key={week.isoDate} className={cn(
                    'border border-slate-300 px-1 py-2 text-center text-[8px] font-bold uppercase text-slate-500',
                    i === currentWeekIdx ? 'bg-blue-100 text-blue-700' : 'bg-slate-100'
                  )}>
                    <div className="font-black">W{week.weekNum}</div>
                    <div className="mt-0.5 font-normal normal-case text-slate-400" style={{ fontSize: '7px' }}>{week.label}</div>
                  </td>
                ))}
                <td className="border border-slate-300 bg-slate-100 px-1 py-2 text-center text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Owner /<br />Priority
                </td>
              </tr>

              {/* ── Objective rows ───────────────────────────── */}
              {loadingObjectives ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    <td className={RN}>{6 + i}</td>
                    <td className={cn(CELL, 'px-1 py-4 text-center')}><div className="mx-auto h-3.5 w-3.5 rounded-full bg-slate-200 animate-pulse" /></td>
                    <td className={cn(CELL, 'px-3 py-4')}><div className="h-4 w-3/4 rounded bg-slate-200 animate-pulse" /></td>
                    {Array.from({ length: VISIBLE_WEEKS }).map((__, wi) => (
                      <td key={wi} className={cn(CELL, 'px-1 py-4 text-center')}><div className="mx-auto h-3.5 w-3.5 rounded-full bg-slate-200 animate-pulse" /></td>
                    ))}
                    <td className={cn(CELL, 'px-2 py-4')} />
                  </tr>
                ))
              ) : (
                <>
                  {objs.map((obj, objIdx) => {
                    const objProgress = calcProgress(obj.id)
                    const linkedTasks = obj.tasks ?? []
                    const rowStatuses = Object.values(timelineMap[obj.id] ?? {})
                    const summaryStatus: string | undefined =
                      !rowStatuses.length ? undefined
                      : rowStatuses.every(s => s === 'completed') ? 'completed'
                      : rowStatuses.includes('blocked') ? 'blocked'
                      : rowStatuses.includes('at_risk') ? 'at_risk'
                      : rowStatuses.includes('in_progress') ? 'in_progress'
                      : 'planned'
                    return (
                      <tr key={obj.id} className="group/row">
                        <td className={cn(RN, 'pt-2')}>{6 + objIdx}</td>

                        {/* Sub Obj letter */}
                        <td className={cn(CELL, 'px-1 py-2 text-center align-top')}>
                          <StatusDot status={summaryStatus} />
                          <div className="mt-1 text-[11px] font-black text-slate-600">{OBJ_LETTERS[objIdx % 26]}</div>
                          {objProgress > 0 && (
                            <div className={cn('mt-0.5 text-[9px] font-semibold',
                              objProgress >= 80 ? 'text-emerald-600' : objProgress >= 50 ? 'text-blue-600' : 'text-amber-600'
                            )}>{objProgress}%</div>
                          )}
                        </td>

                        {/* Major Tasks column — objective + hierarchical tasks */}
                        <td className={cn(CELL, 'px-3 py-2 align-top')}>
                          <div className="flex items-start gap-1.5 group/edit">
                            <span className="text-[10px] font-bold text-slate-400 shrink-0 mt-[1px]">{objIdx + 1}.</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start gap-1">
                                <InlineEdit
                                  value={obj.title}
                                  onSave={v => updateObjective.mutate({ objId: obj.id, data: { title: v } })}
                                  className="text-[12px] font-semibold text-slate-900 leading-5"
                                />
                                <button
                                  onClick={() => confirm(`Delete "${obj.title}"?`) && deleteObjective.mutate(obj.id)}
                                  className="opacity-0 group-hover/edit:opacity-100 text-slate-200 hover:text-red-500 transition-all shrink-0 mt-0.5"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </button>
                              </div>
                              {/* Hierarchical sub-tasks */}
                              {linkedTasks.length > 0 ? (
                                <div className="mt-1 space-y-0.5">
                                  {linkedTasks.map((task, ti) => (
                                    <div key={task.id} className="flex items-baseline gap-1.5 pl-2">
                                      <span className="text-[9px] text-slate-400 shrink-0 font-mono">{objIdx + 1}.{ti + 1}</span>
                                      <span className="text-[10px] text-slate-600 leading-4">{task.title}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="mt-1 pl-2 text-[10px] italic text-slate-300">No linked tasks</div>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Weekly status dots */}
                        {weeks.map((week, wi) => (
                          <td key={week.isoDate} className={cn(CELL, 'px-1 py-3 text-center align-middle', wi === currentWeekIdx && 'bg-blue-50/50')}>
                            <StatusDot status={timelineMap[obj.id]?.[week.isoDate]} onClick={() => handleDotClickFull(obj.id, week.isoDate)} />
                          </td>
                        ))}

                        {/* Owner */}
                        <td className={cn(CELL, 'px-2 py-3 text-center align-middle')}>
                          <OwnerSelect
                            value={obj.owner_id ?? ''}
                            members={wsMembers}
                            onChange={ownerId => updateObjective.mutate({ objId: obj.id, data: { owner_id: ownerId || null } })}
                          />
                        </td>
                      </tr>
                    )
                  })}

                  {/* Filler rows */}
                  {Array.from({ length: Math.max(MIN_OBJECTIVE_ROWS - objs.length, 0) }).map((_, fi) => (
                    <tr key={`filler-${fi}`}>
                      <td className={RN}>{6 + objs.length + fi}</td>
                      <td className={cn(CELL, 'py-4')} />
                      <td className={cn(CELL, 'px-3 py-4')}>
                        {objs.length === 0 && fi === 0 && <span className="text-[11px] italic text-slate-300">Add the first objective below to begin tracking.</span>}
                      </td>
                      {Array.from({ length: VISIBLE_WEEKS }).map((__, wi) => (
                        <td key={wi} className={cn(CELL, 'py-4', wi === currentWeekIdx && 'bg-blue-50/40')} />
                      ))}
                      <td className={cn(CELL)} />
                    </tr>
                  ))}
                </>
              )}

              {/* ── Add objective row ─────────────────────────── */}
              <tr>
                <td className={RN}>{6 + visibleObjRows}</td>
                <td className={cn(CELL, 'px-1 py-3 text-center align-middle')}>
                  <Plus className="mx-auto h-3.5 w-3.5 text-slate-400" />
                </td>
                <td colSpan={VISIBLE_WEEKS + 1} className={cn(CELL, 'px-3 py-2')}>
                  <div className="flex items-center gap-3">
                    <input
                      value={newObjTitle}
                      onChange={e => setNewObjTitle(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && newObjTitle.trim() && createObjective.mutate(newObjTitle.trim())}
                      placeholder="Type a new objective and press Enter…"
                      className="flex-1 border-none bg-transparent px-0 py-1 text-sm text-slate-700 outline-none placeholder:text-slate-300"
                    />
                    <button
                      onClick={() => createObjective.mutate(newObjTitle.trim())}
                      disabled={createObjective.isPending || !newObjTitle.trim()}
                      className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors shrink-0"
                    >
                      {createObjective.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><Plus className="h-3.5 w-3.5" /> Add objective</>}
                    </button>
                  </div>
                </td>
              </tr>

              {/* ── People row ────────────────────────────────── */}
              <tr>
                <td className={RN}>{7 + visibleObjRows}</td>
                <td colSpan={VISIBLE_WEEKS + 2} className="border border-slate-300 bg-slate-100 px-3 py-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  # People working on the project: {wsMembers.length}
                </td>
              </tr>

              {/* ── OPPM Summary section header ───────────────── */}
              <tr>
                <td className={RN}>{8 + visibleObjRows}</td>
                <td colSpan={VISIBLE_WEEKS + 2} className="border border-slate-300 bg-slate-700 px-3 py-1.5">
                  <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white">OPPM Summary</p>
                </td>
              </tr>

              {/* ── Summary rows: X-diagram + Deliverables + Forecast ── */}
              <tr>
                <td className={cn(RN, 'pt-2')} rowSpan={3}>{9 + visibleObjRows}</td>

                {/* X-diagram — spans Sub Obj + Major Tasks cols, 3 rows */}
                <td colSpan={2} rowSpan={3} className={cn(CELL, 'p-0 align-top')}>
                  <div className="relative overflow-hidden bg-white" style={{ minHeight: '220px', height: '100%' }}>
                    {/* Diagonal X lines */}
                    <svg className="absolute inset-0 h-full w-full pointer-events-none" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                      <line x1="0" y1="0" x2="100%" y2="100%" stroke="#cbd5e1" strokeWidth="1.5" />
                      <line x1="100%" y1="0" x2="0" y2="100%" stroke="#cbd5e1" strokeWidth="1.5" />
                    </svg>
                    {/* Quadrant labels */}
                    <div className="absolute left-4 top-4 text-[9px] font-bold text-slate-500 uppercase tracking-wide">Major Tasks</div>
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[9px] font-bold text-slate-500 uppercase tracking-wide text-right">Target<br />Dates</div>
                    <div className="absolute bottom-10 left-4 text-[9px] font-bold text-slate-500 uppercase tracking-wide">Sub Objectives</div>
                    <div className="absolute bottom-10 right-4 text-[9px] font-bold text-slate-500 uppercase tracking-wide text-right">Costs</div>
                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 text-[9px] font-bold text-slate-500 uppercase tracking-wide whitespace-nowrap">Summary &amp; Forecast</div>
                    {/* Centre snapshot card */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="rounded-xl border border-slate-200 bg-white/96 px-5 py-4 text-center shadow-md">
                        <Target className="mx-auto h-5 w-5 text-blue-600" />
                        <div className="mt-1.5 text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">Sheet Snapshot</div>
                        <div className={cn('mt-1.5 text-3xl font-black tabular-nums',
                          overallProgress >= 80 ? 'text-emerald-600' : overallProgress >= 50 ? 'text-blue-600' : overallProgress > 0 ? 'text-amber-600' : 'text-slate-300'
                        )}>{overallProgress}%</div>
                        <div className="mt-1 text-[10px] text-slate-500">{objs.length} obj · {totalTaskCount} tasks</div>
                      </div>
                    </div>
                  </div>
                </td>

                {/* Summary Deliverables */}
                <td colSpan={5} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <p className={LBL}>Summary Deliverables</p>
                  <div className="mt-1.5">
                    <EditableList items={meta.summary_deliverables} onSave={items => updateMeta.mutate({ summary_deliverables: items })} />
                  </div>
                </td>
                {/* Forecast */}
                <td colSpan={VISIBLE_WEEKS - 4} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <p className={LBL}>Forecast</p>
                  <div className="mt-1.5">
                    <InlineTextarea value={meta.forecast} onSave={v => updateMeta.mutate({ forecast: v })} emptyMessage="Click to add summary forecast…" />
                  </div>
                </td>
              </tr>

              {/* Risks row */}
              <tr>
                <td colSpan={VISIBLE_WEEKS + 1} className={cn(CELL, 'px-3 py-2 align-top')}>
                  <p className={LBL}>Risk Register</p>
                  <div className="mt-1.5">
                    <RiskEditor items={meta.risks} onSave={items => updateMeta.mutate({ risks: items })} />
                  </div>
                </td>
              </tr>

              {/* Spacer row */}
              <tr>
                <td colSpan={VISIBLE_WEEKS + 1} className={cn(CELL, 'py-2')} />
              </tr>

              {/* ── Cost section header ───────────────────────── */}
              <tr>
                <td className={RN}>{12 + visibleObjRows}</td>
                <td colSpan={VISIBLE_WEEKS + 2} className="border border-slate-300 bg-slate-100 px-3 py-1.5 align-middle">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Cost / Other Metrics</span>
                    <button
                      onClick={() => setShowAddCost(v => !v)}
                      className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-medium text-slate-600 hover:bg-slate-50"
                    >
                      <Plus className="h-3 w-3" />
                      {showAddCost ? 'Cancel' : 'Add cost item'}
                    </button>
                  </div>
                </td>
              </tr>

              {/* ── Cost body ─────────────────────────────────── */}
              <tr>
                <td className={RN}>{13 + visibleObjRows}</td>
                <td colSpan={VISIBLE_WEEKS + 2} className={cn(CELL, 'p-0')}>
                  <table className="w-full border-collapse text-[11px]">
                    <thead>
                      <tr className="bg-slate-50">
                        <th className="border-b border-slate-200 px-3 py-1.5 text-left text-[9px] font-bold uppercase tracking-[0.12em] text-slate-500" style={{ width: '22%' }}>Category</th>
                        <th className="border-b border-slate-200 px-3 py-1.5 text-left text-[9px] font-bold uppercase tracking-[0.12em] text-slate-500" style={{ width: '50%' }}>Planned / Actual</th>
                        <th className="border-b border-slate-200 px-3 py-1.5 text-left text-[9px] font-bold uppercase tracking-[0.12em] text-slate-500">Notes</th>
                        <th className="border-b border-slate-200 w-6" />
                      </tr>
                    </thead>
                    <tbody>
                      {costs.length === 0 && !showAddCost && (
                        <tr><td colSpan={4} className="px-4 py-6 text-center text-[11px] text-slate-400">No cost items yet. Add one to track planned vs actual.</td></tr>
                      )}
                      {costs.map(cost => (
                        <CostRow
                          key={cost.id}
                          cost={cost}
                          maxAmount={maxCostAmount}
                          onUpdate={data => updateCostMut.mutate({ costId: cost.id, data })}
                          onDelete={() => confirm(`Delete "${cost.category}"?`) && deleteCostMut.mutate(cost.id)}
                        />
                      ))}
                      {showAddCost && (
                        <tr>
                          <td className="px-3 py-2">
                            <input value={newCost.category} onChange={e => setNewCost(c => ({ ...c, category: e.target.value }))} placeholder="Category" className="w-full rounded border border-gray-300 px-2 py-1 text-xs outline-none focus:border-blue-500" />
                          </td>
                          <td className="px-3 py-2">
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <label className="mb-1 block text-[9px] font-medium text-gray-400">Planned</label>
                                <input type="number" value={newCost.planned_amount || ''} onChange={e => setNewCost(c => ({ ...c, planned_amount: parseFloat(e.target.value) || 0 }))} placeholder="0" className="w-full rounded border border-gray-300 px-2 py-1 text-right text-xs outline-none focus:border-blue-500" />
                              </div>
                              <div>
                                <label className="mb-1 block text-[9px] font-medium text-gray-400">Actual</label>
                                <input type="number" value={newCost.actual_amount || ''} onChange={e => setNewCost(c => ({ ...c, actual_amount: parseFloat(e.target.value) || 0 }))} placeholder="0" className="w-full rounded border border-gray-300 px-2 py-1 text-right text-xs outline-none focus:border-blue-500" />
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <input value={newCost.description} onChange={e => setNewCost(c => ({ ...c, description: e.target.value }))} placeholder="Notes" className="w-full rounded border border-gray-300 px-2 py-1 text-xs outline-none focus:border-blue-500" />
                          </td>
                          <td className="px-2 py-2 text-center">
                            <button onClick={() => newCost.category.trim() && createCostMut.mutate(newCost)} className="text-emerald-600 hover:text-emerald-700"><Check className="h-4 w-4" /></button>
                          </td>
                        </tr>
                      )}
                      {/* Totals row */}
                      {costs.length > 0 && (
                        <tr className="bg-slate-50 font-semibold">
                          <td className="px-3 py-2 text-[10px] text-slate-500 uppercase tracking-wide">Totals</td>
                          <td className="px-3 py-2">
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="text-blue-700">Planned: {(costData?.total_planned ?? 0).toLocaleString()}</span>
                              <span className={cn(costVariance > 0 ? 'text-red-600' : 'text-emerald-600')}>
                                Actual: {(costData?.total_actual ?? 0).toLocaleString()}
                                {costVariance !== 0 && <span className="ml-2 text-[10px]">({costVariance > 0 ? '+' : ''}{costVariance.toLocaleString()})</span>}
                              </span>
                            </div>
                          </td>
                          <td colSpan={2} />
                        </tr>
                      )}
                    </tbody>
                  </table>
                </td>
              </tr>
            </tbody>
          </table>

          {/* ── Right sidebar: Priority + Legend ─────────────── */}
          <table className="ml-2 border-collapse table-fixed bg-white text-[11px] shrink-0" style={{ width: '258px' }}>
            <colgroup>
              <col style={{ width: '30px' }} />
              <col style={{ width: '76px' }} />
              <col style={{ width: '76px' }} />
              <col style={{ width: '76px' }} />
            </colgroup>
            <thead>
              <tr>
                <th className={HD} />
                <th className={HD}>A</th>
                <th className={HD}>B</th>
                <th className={HD}>C</th>
              </tr>
            </thead>
            <tbody>
              {/* Priority header */}
              <tr>
                <td className={RN}>1</td>
                <td colSpan={3} className={cn(CELL, 'px-2 py-1.5 bg-slate-800')}>
                  <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-white">Priority</p>
                </td>
              </tr>
              <tr>
                <td className={RN}>2</td>
                {['A', 'B', 'C'].map(l => (
                  <td key={l} className="border border-slate-300 bg-white px-2 py-2 text-center text-[13px] font-black text-slate-800">{l}</td>
                ))}
              </tr>
              <tr>
                <td className={RN}>3</td>
                {['Primary / Owner', 'Primary Helper', 'Secondary Helper'].map(t => (
                  <td key={t} className={cn(CELL, 'px-2 py-2 text-[10px] text-slate-600 leading-4')}>{t}</td>
                ))}
              </tr>

              {/* Spacer */}
              <tr>
                <td className={RN}>4</td>
                <td colSpan={3} className={cn(CELL, 'py-2 bg-slate-50')} />
              </tr>

              {/* Project Identity Symbol header */}
              <tr>
                <td className={RN}>5</td>
                <td colSpan={3} className={cn(CELL, 'px-2 py-1.5 bg-slate-800')}>
                  <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-white">Project Identity Symbol</p>
                </td>
              </tr>
              {/* Status symbols */}
              <tr>
                <td className={RN}>6</td>
                {[
                  { status: 'planned',     label: 'Start' },
                  { status: 'in_progress', label: 'In Progress' },
                  { status: 'completed',   label: 'Complete' },
                ].map(({ status, label }) => (
                  <td key={status} className={cn(CELL, 'px-2 py-2 text-center')}>
                    <StatusDot status={status} />
                    <div className="mt-1 text-[10px] text-slate-600">{label}</div>
                  </td>
                ))}
              </tr>
              {/* RAG colors */}
              <tr>
                <td className={RN}>7</td>
                <td className="border border-slate-300 bg-emerald-500 px-2 py-2 text-center text-[10px] font-bold text-white">Green</td>
                <td className="border border-slate-300 bg-amber-400 px-2 py-2 text-center text-[10px] font-bold text-white">Yellow</td>
                <td className="border border-slate-300 bg-red-600 px-2 py-2 text-center text-[10px] font-bold text-white">Red</td>
              </tr>
              <tr>
                <td className={RN}>8</td>
                <td className="border border-slate-300 bg-emerald-50 px-2 py-2 text-center text-[10px] font-semibold text-emerald-800">Good</td>
                <td className="border border-slate-300 bg-amber-50 px-2 py-2 text-center text-[10px] font-semibold text-amber-800">Average</td>
                <td className="border border-slate-300 bg-red-50 px-2 py-2 text-center text-[10px] font-semibold text-red-800">Bad</td>
              </tr>

              {/* Spacer */}
              <tr>
                <td className={RN}>9</td>
                <td colSpan={3} className={cn(CELL, 'py-2 bg-slate-50')} />
              </tr>

              {/* Window info */}
              <tr>
                <td className={RN}>10</td>
                <td colSpan={3} className={cn(CELL, 'px-2 py-2')}>
                  <p className={LBL}>Current Sheet Window</p>
                  <p className="mt-0.5 text-[11px] font-semibold text-slate-900">{visibleWindowLabel}</p>
                </td>
              </tr>

              {/* Quick stats */}
              <tr>
                <td className={RN}>11</td>
                <td colSpan={3} className={cn(CELL, 'px-2 py-2')}>
                  <div className="space-y-1">
                    {[
                      { label: 'Timeline attention', val: String(atRiskCount + blockedCount), danger: atRiskCount + blockedCount > 0 },
                      { label: 'Planned budget',  val: (costData?.total_planned ?? 0).toLocaleString() },
                      { label: 'Actual spend',    val: (costData?.total_actual ?? 0).toLocaleString(), danger: costVariance > 0 },
                    ].map(({ label, val, danger }) => (
                      <div key={label} className="flex items-center justify-between gap-2 text-[10px]">
                        <span className="text-slate-500">{label}</span>
                        <span className={cn('font-semibold tabular-nums', danger ? 'text-red-600' : 'text-slate-900')}>{val}</span>
                      </div>
                    ))}
                  </div>
                </td>
              </tr>

              {/* Team */}
              <tr>
                <td className={RN}>12</td>
                <td colSpan={3} className={cn(CELL, 'px-2 py-2')}>
                  <p className={LBL}>Active Team</p>
                  <div className="mt-1.5 space-y-1">
                    <div className="flex items-center justify-between gap-1 text-[10px]">
                      <span className="text-slate-500 shrink-0">Project Leader</span>
                      <span className="truncate font-semibold text-slate-900">{leaderName}</span>
                    </div>
                    {wsMembers.slice(0, 5).map((m, i) => (
                      <div key={m.id} className="flex items-center justify-between gap-1 text-[10px]">
                        <span className="text-slate-400 shrink-0">Member {i + 1}</span>
                        <span className="truncate text-slate-700">{m.display_name || m.email.split('@')[0]}</span>
                      </div>
                    ))}
                    {wsMembers.length === 0 && <div className="text-[10px] italic text-slate-300">No members yet</div>}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}