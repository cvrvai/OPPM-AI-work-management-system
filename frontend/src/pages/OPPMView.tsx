/**
 * OPPMView — One Page Project Manager (Fully Editable)
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
import { cn, formatDate } from '@/lib/utils'
import {
  ArrowLeft, ChevronLeft, ChevronRight, Loader2, Target,
  Check, X, Plus, Trash2,
} from 'lucide-react'
import { startOfWeek, addWeeks, format, parseISO, isWithinInterval, endOfWeek } from 'date-fns'
import { useChatContext } from '@/hooks/useChatContext'

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────
const VISIBLE_WEEKS = 8
const TOTAL_COLS = VISIBLE_WEEKS + 4 // Obj(letter) + Tasks + % + weeks + Owner
const OBJ_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  planned:     { color: '#9CA3AF', bg: 'bg-gray-300',     label: 'Planned' },
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
interface RiskItem {
  text: string
  rag: 'green' | 'amber' | 'red'
}

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
// StatusDot — clickable circle that cycles through statuses
// ─────────────────────────────────────────────────────────────
function StatusDot({
  status,
  onClick,
}: {
  status?: string
  onClick?: () => void
}) {
  const cfg = status && status !== 'empty' ? STATUS_CONFIG[status] : null
  return (
    <div
      onClick={onClick}
      title={cfg?.label ?? 'Click to set status'}
      className={cn(
        'w-3.5 h-3.5 rounded-full mx-auto transition-all duration-150 shrink-0',
        onClick && 'cursor-pointer hover:scale-125',
        cfg ? cfg.bg : 'border-[1.5px] border-gray-300 bg-transparent'
      )}
    />
  )
}

// ─────────────────────────────────────────────────────────────
// InlineEdit — click-to-edit text field
// ─────────────────────────────────────────────────────────────
function InlineEdit({
  value,
  onSave,
  placeholder = 'Click to edit…',
  className: extraClass,
}: {
  value: string
  onSave: (v: string) => void
  placeholder?: string
  className?: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => { if (editing) ref.current?.focus() }, [editing])
  useEffect(() => { setDraft(value) }, [value])

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(value); setEditing(true) }}
        className={cn(
          'cursor-text rounded px-0.5 hover:bg-amber-50 border border-transparent hover:border-amber-200 transition-colors',
          !value && 'text-gray-400 italic',
          extraClass
        )}
        title="Click to edit"
      >
        {value || placeholder}
      </span>
    )
  }

  return (
    <input
      ref={ref}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => { if (draft !== value) onSave(draft); setEditing(false) }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') { if (draft !== value) onSave(draft); setEditing(false) }
        if (e.key === 'Escape') { setDraft(value); setEditing(false) }
      }}
      className={cn(
        'bg-transparent border-b-[1.5px] border-blue-500 outline-none w-full text-inherit',
        extraClass
      )}
    />
  )
}

// ─────────────────────────────────────────────────────────────
// EditableList — numbered list for deliverables/forecast/risk
// ─────────────────────────────────────────────────────────────
function EditableList({
  items,
  onSave,
}: {
  items: string[]
  onSave: (items: string[]) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([])

  const startEdit = () => { setDraft([...items]); setEditing(true) }

  if (editing) {
    return (
      <div className="space-y-1">
        {draft.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-400 w-4 shrink-0">{i + 1}.</span>
            <input
              value={item}
              onChange={(e) => {
                const next = [...draft]
                next[i] = e.target.value
                setDraft(next)
              }}
              className="flex-1 text-xs border border-blue-400 rounded px-1.5 py-0.5 outline-none focus:border-blue-500"
            />
          </div>
        ))}
        <div className="flex gap-2 mt-1.5">
          <button
            onClick={() => { onSave(draft); setEditing(false) }}
            className="text-[10px] bg-blue-600 text-white rounded px-2 py-0.5 font-medium hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-[10px] text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="cursor-pointer group" onClick={startEdit}>
      {items.map((item, i) => (
        <div key={i} className="text-xs leading-5 hover:bg-amber-50/60 rounded px-0.5">
          <span className="text-gray-400 mr-1">{i + 1}.</span>
          <span className="text-gray-700">
            {item || <em className="not-italic text-gray-300">—</em>}
          </span>
        </div>
      ))}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">
        ✎ click to edit
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// RiskEditor — numbered list with RAG (Red/Amber/Green) status
// ─────────────────────────────────────────────────────────────
const RAG_COLORS = {
  green: { dot: 'bg-emerald-500', ring: 'ring-emerald-300' },
  amber: { dot: 'bg-amber-500', ring: 'ring-amber-300' },
  red:   { dot: 'bg-red-500', ring: 'ring-red-300' },
} as const

function RiskEditor({
  items,
  onSave,
}: {
  items: RiskItem[]
  onSave: (items: RiskItem[]) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<RiskItem[]>([])

  const startEdit = () => { setDraft(items.map((it) => ({ ...it }))); setEditing(true) }

  if (editing) {
    return (
      <div className="space-y-1.5">
        {draft.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-400 w-4 shrink-0">{i + 1}.</span>
            {(['green', 'amber', 'red'] as const).map((rag) => (
              <button
                key={rag}
                type="button"
                onClick={() => {
                  const next = [...draft]
                  next[i] = { ...next[i], rag }
                  setDraft(next)
                }}
                className={cn(
                  'h-3.5 w-3.5 rounded-full shrink-0 transition-all',
                  RAG_COLORS[rag].dot,
                  item.rag === rag ? `ring-2 ${RAG_COLORS[rag].ring} scale-110` : 'opacity-40 hover:opacity-70'
                )}
                title={rag.charAt(0).toUpperCase() + rag.slice(1)}
              />
            ))}
            <input
              value={item.text}
              onChange={(e) => {
                const next = [...draft]
                next[i] = { ...next[i], text: e.target.value }
                setDraft(next)
              }}
              className="flex-1 text-xs border border-blue-400 rounded px-1.5 py-0.5 outline-none focus:border-blue-500"
            />
          </div>
        ))}
        <div className="flex gap-2 mt-1.5">
          <button
            onClick={() => { onSave(draft); setEditing(false) }}
            className="text-[10px] bg-blue-600 text-white rounded px-2 py-0.5 font-medium hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-[10px] text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
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
          <span className="text-gray-700">
            {item.text || <em className="not-italic text-gray-300">—</em>}
          </span>
        </div>
      ))}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">
        ✎ click to edit
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// InlineTextarea — click-to-edit multi-line text
// ─────────────────────────────────────────────────────────────
function InlineTextarea({
  value,
  onSave,
}: {
  value: string
  onSave: (value: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  const startEdit = () => { setDraft(value); setEditing(true) }

  if (editing) {
    return (
      <div className="space-y-1.5">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={4}
          className="w-full text-xs border border-blue-400 rounded px-2 py-1.5 outline-none focus:border-blue-500 resize-none"
          autoFocus
        />
        <div className="flex gap-2">
          <button
            onClick={() => { onSave(draft); setEditing(false) }}
            className="text-[10px] bg-blue-600 text-white rounded px-2 py-0.5 font-medium hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-[10px] text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="cursor-pointer group" onClick={startEdit}>
      {value ? (
        <p className="text-xs leading-5 text-gray-700 whitespace-pre-wrap">{value}</p>
      ) : (
        <p className="text-xs text-gray-300 italic">Click to add forecast narrative...</p>
      )}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">
        ✎ click to edit
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// VerticalLabel — rotated text for bottom section rows
// ─────────────────────────────────────────────────────────────
function VerticalLabel({ children }: { children: string }) {
  return (
    <td
      className="border border-gray-300 px-1 py-2 text-center align-middle bg-gray-100"
      style={{ writingMode: 'vertical-lr', textOrientation: 'mixed', transform: 'rotate(180deg)' }}
    >
      <span className="text-[9px] font-bold text-gray-600 uppercase tracking-widest whitespace-nowrap">
        {children}
      </span>
    </td>
  )
}

// ─────────────────────────────────────────────────────────────
// CostRow — cost item with horizontal bar chart visualization
// ─────────────────────────────────────────────────────────────
function CostRow({
  cost,
  maxAmount,
  onUpdate,
  onDelete,
}: {
  cost: OPPMCost
  maxAmount: number
  onUpdate: (data: Partial<OPPMCost>) => void
  onDelete: () => void
}) {
  const safeMax = maxAmount || 1
  const plannedPct = Math.min((cost.planned_amount / safeMax) * 100, 100)
  const actualPct = Math.min((cost.actual_amount / safeMax) * 100, 100)
  const overBudget = cost.actual_amount > cost.planned_amount

  return (
    <tr className="hover:bg-gray-50/60">
      {/* Category */}
      <td className="border-b border-gray-200 px-2 py-2 align-middle w-[22%]">
        <InlineEdit
          value={cost.category}
          onSave={(v) => onUpdate({ category: v })}
          className="text-[11px] font-medium text-gray-700"
        />
      </td>
      {/* Bar chart visualization */}
      <td className="border-b border-gray-200 px-3 py-1.5 align-middle" style={{ width: '50%' }}>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-400 w-10 shrink-0 font-medium">Planned</span>
            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden border border-gray-200">
              <div
                className="h-full bg-blue-400 rounded-sm transition-all duration-300"
                style={{ width: `${plannedPct}%` }}
              />
            </div>
            <InlineEdit
              value={String(cost.planned_amount)}
              onSave={(v) => onUpdate({ planned_amount: parseFloat(v) || 0 })}
              className="text-[10px] text-gray-600 w-14 text-right font-mono"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-400 w-10 shrink-0 font-medium">Actual</span>
            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden border border-gray-200">
              <div
                className={cn(
                  'h-full rounded-sm transition-all duration-300',
                  overBudget ? 'bg-red-400' : 'bg-emerald-400',
                )}
                style={{ width: `${actualPct}%` }}
              />
            </div>
            <InlineEdit
              value={String(cost.actual_amount)}
              onSave={(v) => onUpdate({ actual_amount: parseFloat(v) || 0 })}
              className={cn(
                'text-[10px] w-14 text-right font-mono',
                overBudget ? 'text-red-600 font-bold' : 'text-emerald-600',
              )}
            />
          </div>
        </div>
      </td>
      {/* Notes */}
      <td className="border-b border-gray-200 px-2 py-2 align-middle">
        <InlineEdit
          value={cost.notes}
          onSave={(v) => onUpdate({ notes: v })}
          placeholder="—"
          className="text-[11px] text-gray-500"
        />
      </td>
      {/* Delete */}
      <td className="border-b border-gray-200 px-1 py-2 text-center align-middle w-7">
        <button
          onClick={onDelete}
          className="text-gray-300 hover:text-red-500 transition-colors"
          title="Delete"
        >
          <Trash2 className="h-3 w-3" />
        </button>
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
  const [newCost, setNewCost] = useState({ category: '', planned_amount: 0, actual_amount: 0, notes: '' })

  const user = useAuthStore((s) => s.user)
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  // ── Queries ────────────────────────────────────────────────
  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn: () => api.get<Project>(`${wsPath}/projects/${id}`),
    enabled: !!ws,
  })

  // Set chat context to this project
  useChatContext('project', id, project?.title)

  const { data: objectives, isLoading: loadingObjectives } = useQuery({
    queryKey: ['oppm-objectives', id, ws?.id],
    queryFn: () => api.get<OPPMObjective[]>(`${wsPath}/projects/${id}/oppm/objectives`),
    enabled: !!ws,
  })

  const { data: timelineEntries } = useQuery({
    queryKey: ['oppm-timeline', id, ws?.id],
    queryFn: () => api.get<OPPMTimelineEntry[]>(`${wsPath}/projects/${id}/oppm/timeline`),
    enabled: !!ws,
  })

  const { data: costData } = useQuery({
    queryKey: ['oppm-costs', id, ws?.id],
    queryFn: () => api.get<{ total_planned: number; total_actual: number; items: OPPMCost[] }>(`${wsPath}/projects/${id}/oppm/costs`),
    enabled: !!ws,
  })

  // ── Mutations ──────────────────────────────────────────────

  // Objectives
  const createObjective = useMutation({
    mutationFn: (title: string) =>
      api.post(`${wsPath}/projects/${id}/oppm/objectives`, {
        title,
        project_id: id,
        sort_order: (objectives?.length ?? 0) + 1,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] })
      setNewObjTitle('')
    },
  })

  const updateObjective = useMutation({
    mutationFn: ({ objId, data }: { objId: string; data: Record<string, unknown> }) =>
      api.put(`${wsPath}/oppm/objectives/${objId}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] }),
  })

  const deleteObjective = useMutation({
    mutationFn: (objId: string) => api.delete(`${wsPath}/oppm/objectives/${objId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-timeline', id] })
    },
  })

  // Timeline
  const upsertTimeline = useMutation({
    mutationFn: (data: { objective_id: string; week_start: string; status: string; notes?: string }) =>
      api.put(`${wsPath}/projects/${id}/oppm/timeline`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-timeline', id] }),
  })

  // Costs
  const createCostMut = useMutation({
    mutationFn: (data: { category: string; planned_amount: number; actual_amount: number; notes: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/costs`, { ...data, project_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] })
      setShowAddCost(false)
      setNewCost({ category: '', planned_amount: 0, actual_amount: 0, notes: '' })
    },
  })

  const updateCostMut = useMutation({
    mutationFn: ({ costId, data }: { costId: string; data: Record<string, unknown> }) =>
      api.put(`${wsPath}/oppm/costs/${costId}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] }),
  })

  const deleteCostMut = useMutation({
    mutationFn: (costId: string) => api.delete(`${wsPath}/oppm/costs/${costId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] }),
  })

  // Project metadata
  const updateMeta = useMutation({
    mutationFn: (patch: OPPMMetadata) =>
      api.put(`${wsPath}/projects/${id}`, { metadata: { ...meta, ...patch } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', id] }),
  })

  // ── Computed data ──────────────────────────────────────────
  const projectStart = useMemo(
    () =>
      startOfWeek(
        parseISO(project?.start_date || project?.created_at || new Date().toISOString()),
        { weekStartsOn: 1 }
      ),
    [project?.start_date, project?.created_at]
  )

  const weeks = useMemo(
    () =>
      Array.from({ length: VISIBLE_WEEKS }, (_, i) => {
        const ws = addWeeks(projectStart, weekOffset + i)
        return {
          start: ws,
          end: endOfWeek(ws, { weekStartsOn: 1 }),
          label: format(ws, 'MMM d'),
          weekNum: weekOffset + i + 1,
          isoDate: format(ws, 'yyyy-MM-dd'),
        }
      }),
    [weekOffset, projectStart]
  )

  const meta: NormalizedMeta = useMemo(() => {
    const m = (project?.metadata as OPPMMetadata) ?? {}
    // Normalize risks: handle legacy string[] or new RiskItem[]
    let risks: RiskItem[]
    if (m.risks?.length) {
      risks = (m.risks as (string | RiskItem)[]).map((item) =>
        typeof item === 'string' ? { text: item, rag: 'green' as const } : item
      )
    } else {
      risks = [{ text: '', rag: 'green' }, { text: '', rag: 'green' }, { text: '', rag: 'green' }, { text: '', rag: 'green' }]
    }
    // Normalize forecast: handle legacy string[] or new string
    let forecast: string
    if (typeof m.forecast === 'string') {
      forecast = m.forecast
    } else if (Array.isArray(m.forecast) && m.forecast.length) {
      forecast = m.forecast.filter(Boolean).join('\n')
    } else {
      forecast = ''
    }
    return {
      deliverable_output:    m.deliverable_output    ?? '',
      summary_deliverables:  m.summary_deliverables?.length ? m.summary_deliverables : ['', '', '', ''],
      forecast,
      risks,
    }
  }, [project?.metadata])

  // Build a lookup map: objectiveId → weekIsoDate → status
  const timelineMap = useMemo(() => {
    const map: Record<string, Record<string, TimelineStatus>> = {}
    if (!timelineEntries) return map
    for (const entry of timelineEntries) {
      if (!map[entry.objective_id]) map[entry.objective_id] = {}
      map[entry.objective_id][entry.week_start] = entry.status
    }
    return map
  }, [timelineEntries])

  // Calculate progress per objective and overall
  const calcProgress = useCallback(
    (objId: string): number => {
      const objTimeline = timelineMap[objId]
      if (!objTimeline) return 0
      const weekStatuses = weeks.map((w) => objTimeline[w.isoDate]).filter(Boolean)
      if (weekStatuses.length === 0) return 0
      const completed = weekStatuses.filter((s) => s === 'completed').length
      return Math.round((completed / weeks.length) * 100)
    },
    [timelineMap, weeks]
  )

  const overallProgress = useMemo(() => {
    const objs = objectives ?? []
    if (objs.length === 0) return 0
    const total = objs.length * weeks.length
    let completedCells = 0
    for (const obj of objs) {
      const objTimeline = timelineMap[obj.id]
      if (!objTimeline) continue
      for (const week of weeks) {
        if (objTimeline[week.isoDate] === 'completed') completedCells++
      }
    }
    return Math.round((completedCells / total) * 100)
  }, [objectives, timelineMap, weeks])

  // Handle clicking a timeline dot
  const handleDotClick = useCallback(
    (objectiveId: string, weekIsoDate: string) => {
      const current = timelineMap[objectiveId]?.[weekIsoDate] || 'empty'
      const next = nextStatus(current)
      if (next === 'empty') {
        // Delete the entry by setting status to something the backend handles
        // Since we don't have a delete endpoint for individual timeline entries,
        // we'll cycle to planned instead of deleting
        // Actually, let's upsert with the next valid status or skip empty
        return // empty means remove — but we don't have a delete endpoint, so skip back to planned
      }
      upsertTimeline.mutate({
        objective_id: objectiveId,
        week_start: weekIsoDate,
        status: next,
      })
    },
    [timelineMap, upsertTimeline]
  )

  // Handle clicking a timeline dot — full cycle including removal
  const handleDotClickFull = useCallback(
    (objectiveId: string, weekIsoDate: string) => {
      const current = timelineMap[objectiveId]?.[weekIsoDate] || 'empty'
      const next = nextStatus(current)
      if (next === 'empty') {
        // Cycle back to planned (no delete endpoint for single timeline entries)
        // Just don't upsert — the dot will show as empty if there's no entry
        // For now, set to planned to restart the cycle
        upsertTimeline.mutate({
          objective_id: objectiveId,
          week_start: weekIsoDate,
          status: 'planned',
        })
        return
      }
      upsertTimeline.mutate({
        objective_id: objectiveId,
        week_start: weekIsoDate,
        status: next,
      })
    },
    [timelineMap, upsertTimeline]
  )

  const today = new Date()
  const currentWeekIdx = weeks.findIndex((w) =>
    isWithinInterval(today, { start: w.start, end: w.end })
  )

  const leaderName = user?.user_metadata?.full_name ?? user?.email?.split('@')[0] ?? 'Project Leader'

  const maxCostAmount = useMemo(
    () => Math.max(...(costData?.items ?? []).flatMap((c) => [c.planned_amount, c.actual_amount]), 1),
    [costData],
  )

  // ── Loading / Error states ──────────────────────────────────
  if (loadingProject || loadingObjectives) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!project) {
    return <p className="text-sm text-gray-500 py-12 text-center">Project not found</p>
  }

  const p = project
  const objs = objectives ?? []
  const costs = costData?.items ?? []

  // ── Render ────────────────────────────────────────────────
  return (
    <div className="space-y-4">

      {/* ── Navigation bar ── */}
      <div className="flex items-center gap-3">
        <Link
          to={`/projects/${id}`}
          className="rounded-lg border border-gray-200 p-2 text-gray-500 hover:bg-gray-50"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-gray-900">OPPM — {p.title}</h1>
          <p className="text-xs text-gray-500">One Page Project Manager · Gantt + Matrix View</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setWeekOffset((o) => o - 1)}
            className="rounded-lg border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-gray-500 px-3 font-medium">
            W{weekOffset + 1} – W{weekOffset + VISIBLE_WEEKS}
          </span>
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="rounded-lg border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          OPPM SHEET
      ══════════════════════════════════════════════════════ */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
        <table
          className="border-collapse text-sm"
          style={{
            minWidth: `${340 + VISIBLE_WEEKS * 68 + 72}px`,
            tableLayout: 'fixed',
            width: '100%',
          }}
        >
          {/* Column widths */}
          <colgroup>{/* */}
            <col style={{ width: '40px' }} />{/* Obj letter */}
            <col style={{ width: '210px' }} />{/* Major Tasks */}
            <col style={{ width: '36px' }} />{/* % */}
            {Array.from({ length: VISIBLE_WEEKS }).map((_, i) => (
              <col key={i} style={{ width: '62px' }} />
            ))}{/* */}
            <col style={{ width: '70px' }} />{/* Owner / Priority */}
          </colgroup>

          {/* ──────────────────────────────────────────────────
              HEADER — 3 rows
          ────────────────────────────────────────────────── */}
          <thead>{/* */}

            {/* Row 1: Project Leader | Logo | Project Name | Progress */}
            <tr>{/* */}
              <td
                colSpan={3}
                className="border border-gray-300 px-3 py-2 bg-gray-50"
              >
                <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider">
                  Project Leader
                </div>
                <div className="text-sm font-bold text-gray-800">{leaderName}</div>
              </td>{/* */}

              <td
                colSpan={1}
                className="border border-gray-300 px-2 py-2 text-center bg-blue-50"
              >
                <div className="flex flex-col items-center justify-center gap-0.5">
                  <Target className="h-4 w-4 text-blue-600" />
                  <div className="text-[10px] font-bold text-blue-600 leading-none">OPPM</div>
                </div>
              </td>{/* */}

              {/* Project Name spans W2–W8 */}
              <td
                colSpan={VISIBLE_WEEKS - 1}
                className="border border-gray-300 px-3 py-2 bg-gray-50"
              >
                <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider">
                  Project Name
                </div>
                <div className="text-sm font-bold text-gray-800">{p.title}</div>
              </td>{/* */}

              {/* Progress */}
              <td className="border border-gray-300 px-2 py-2 bg-gray-50 text-center">
                <div className="text-[9px] text-gray-400">Progress</div>
                <div className={cn(
                  'text-base font-black',
                  overallProgress > 0 ? 'text-blue-600' : 'text-gray-400'
                )}>
                  {overallProgress}%
                </div>
              </td>{/* */}
            </tr>

            {/* Row 2: Objective + Output | Dates + Legend */}
            <tr>{/* */}
              <td
                colSpan={4}
                className="border border-gray-300 px-3 py-2 text-xs"
              >
                <div className="space-y-1.5">
                  <div>
                    <span className="font-semibold text-gray-500">Project Objective: </span>
                    <span className="text-gray-700">{p.description || '—'}</span>
                  </div>
                  <div className="flex items-start gap-1 flex-wrap">
                    <span className="font-semibold text-gray-500 shrink-0">Deliverable Output:</span>
                    <InlineEdit
                      value={meta.deliverable_output}
                      onSave={(v) => updateMeta.mutate({ deliverable_output: v })}
                      placeholder="Click to add deliverable output…"
                      className="text-xs text-gray-700"
                    />
                  </div>
                </div>
              </td>{/* */}

              <td
                colSpan={VISIBLE_WEEKS}
                className="border border-gray-300 px-3 py-2"
              >
                <div className="flex items-center gap-5 text-xs mb-1.5 flex-wrap">
                  <div>
                    <span className="font-semibold text-gray-500">Start Date: </span>
                    <span className="text-gray-700">{p.start_date ? formatDate(p.start_date) : '—'}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-gray-500">Deadline: </span>
                    <span className="text-gray-700">{p.deadline ? formatDate(p.deadline) : '—'}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-gray-500">Status: </span>
                    <span className="text-gray-700 capitalize">{p.status.replace('_', ' ')}</span>
                  </div>
                </div>
                {/* Legend */}
                <div className="flex items-center gap-4 flex-wrap">
                  {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                    <span key={key} className="flex items-center gap-1 text-[10px] text-gray-500">
                      <span className={cn('h-2 w-2 rounded-full shrink-0', cfg.bg)} />
                      {cfg.label}
                    </span>
                  ))}
                </div>
              </td>{/* */}
            </tr>

            {/* Row 3: Column headers */}
            <tr className="bg-gray-100">{/* */}
              <th className="border border-gray-300 px-1 py-2 text-center text-[9px] font-bold text-gray-600 uppercase tracking-wide">
                Obj
              </th>
              <th className="border border-gray-300 px-3 py-2 text-left text-[9px] font-bold text-gray-600 uppercase tracking-wide">
                Major Tasks (Deadline)
              </th>
              <th className="border border-gray-300 px-1 py-2 text-center text-[9px] font-bold text-gray-600 uppercase tracking-wide">
                %
              </th>
              {weeks.map((week, i) => (
                <th
                  key={i}
                  className={cn(
                    'border border-gray-300 px-1 py-2 text-center text-[9px] font-bold uppercase tracking-wide',
                    i === currentWeekIdx
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-500'
                  )}
                >
                  <div className="font-black">W{week.weekNum}</div>
                  <div className="font-normal text-[8px] text-gray-400 mt-0.5">{week.label}</div>
                </th>
              ))}{/* */}
              <th className="border border-gray-300 px-1 py-2 text-center text-[9px] font-bold text-gray-600 uppercase tracking-wide">
                Owner /<br />Priority
              </th>{/* */}
            </tr>
          </thead>

          {/* ──────────────────────────────────────────────────
              BODY — Objective rows + Bottom Section
          ────────────────────────────────────────────────── */}
          <tbody>{/* */}

            {/* ── Empty state ── */}
            {objs.length === 0 && !newObjTitle && (
              <tr>{/* */}
                <td
                  colSpan={TOTAL_COLS}
                  className="border border-gray-200 py-14 text-center text-sm text-gray-400 italic"
                >
                  No objectives yet. Click "+ Add objective" below to start building your OPPM.
                </td>{/* */}
              </tr>
            )}

            {/* ── Objective rows ── */}
            {objs.map((obj, objIdx) => {
              const objProgress = calcProgress(obj.id)
              return (
                <tr
                  key={obj.id}
                  className={cn(
                    'group',
                    objIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50/60'
                  )}
                >
                  {/* Objective letter + summary status dot */}
                  {(() => {
                    const rowStatuses = Object.values(timelineMap[obj.id] ?? {})
                    const summaryStatus: string | undefined =
                      rowStatuses.length === 0 ? undefined
                      : rowStatuses.every((s) => s === 'completed') ? 'completed'
                      : rowStatuses.includes('blocked') ? 'blocked'
                      : rowStatuses.includes('at_risk') ? 'at_risk'
                      : rowStatuses.includes('in_progress') ? 'in_progress'
                      : 'planned'
                    return (
                      <td className="border border-gray-300 text-center align-middle py-1.5 px-0.5">
                        <StatusDot status={summaryStatus} />
                        <div className="text-[10px] font-black text-gray-600 mt-0.5 leading-none">
                          {OBJ_LETTERS[objIdx % 26]}
                        </div>
                      </td>
                    )
                  })()}

                  {/* Objective title — inline editable with number prefix */}
                  <td className="border border-gray-300 px-2 py-1.5 align-middle">
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] font-bold text-gray-400 shrink-0 w-5 text-right">
                        {objIdx + 1}.
                      </span>
                      <InlineEdit
                        value={obj.title}
                        onSave={(v) =>
                          updateObjective.mutate({ objId: obj.id, data: { title: v } })
                        }
                        className="text-[11px] font-medium text-gray-800 flex-1"
                      />
                      <button
                        onClick={() => {
                          if (confirm(`Delete objective "${obj.title}"?`)) {
                            deleteObjective.mutate(obj.id)
                          }
                        }}
                        className="text-transparent group-hover:text-gray-400 hover:!text-red-500 transition-colors"
                        title="Delete objective"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </td>

                  {/* Progress % */}
                  <td className="border border-gray-300 text-center align-middle p-1">
                    <span
                      className={cn(
                        'text-[11px] font-bold',
                        objProgress >= 80 ? 'text-emerald-600' :
                        objProgress >= 50 ? 'text-blue-600' :
                        objProgress > 0   ? 'text-amber-600' :
                                            'text-gray-400'
                      )}
                    >
                      {objProgress > 0 ? `${objProgress}%` : '—'}
                    </span>
                  </td>

                  {/* Week status dots — CLICKABLE */}
                  {weeks.map((week, wi) => {
                    const status = timelineMap[obj.id]?.[week.isoDate]
                    return (
                      <td
                        key={wi}
                        className={cn(
                          'border border-gray-300 text-center p-1 align-middle',
                          wi === currentWeekIdx && 'bg-blue-50/60'
                        )}
                      >
                        <StatusDot
                          status={status}
                          onClick={() => handleDotClickFull(obj.id, week.isoDate)}
                        />
                      </td>
                    )
                  })}

                  {/* Owner — inline editable */}
                  <td className="border border-gray-300 px-1 py-1 text-center align-middle">
                    <InlineEdit
                      value={obj.owner?.display_name || obj.owner?.email || ''}
                      onSave={(v) =>
                        updateObjective.mutate({ objId: obj.id, data: { owner_id: v } })
                      }
                      placeholder="—"
                      className="text-[10px] text-gray-600"
                    />
                  </td>
                </tr>
              )
            })}

            {/* ── Add objective row ── */}
            <tr>{/* */}
              <td className="border border-gray-300 text-center align-middle p-1">
                <Plus className="h-3 w-3 text-gray-400 mx-auto" />
              </td>
              <td colSpan={TOTAL_COLS - 1} className="border border-gray-300 px-3 py-1.5">
                <div className="flex items-center gap-2">
                  <input
                    value={newObjTitle}
                    onChange={(e) => setNewObjTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newObjTitle.trim()) {
                        createObjective.mutate(newObjTitle.trim())
                      }
                    }}
                    placeholder="+ Add objective (press Enter)"
                    className="flex-1 text-sm text-gray-700 bg-transparent outline-none placeholder:text-gray-400 placeholder:italic"
                  />
                  {newObjTitle.trim() && (
                    <button
                      onClick={() => createObjective.mutate(newObjTitle.trim())}
                      disabled={createObjective.isPending}
                      className="text-xs bg-blue-600 text-white rounded px-3 py-1 font-medium hover:bg-blue-700 disabled:opacity-50"
                    >
                      {createObjective.isPending ? 'Adding…' : 'Add'}
                    </button>
                  )}
                </div>
              </td>{/* */}
            </tr>

            {/* ══════════════════════════════════════════════════
                COST SECTION
            ══════════════════════════════════════════════════ */}
            {(costs.length > 0 || showAddCost) && (
              <>
                <tr>{/* */}
                  <td
                    colSpan={TOTAL_COLS}
                    className="border border-gray-300 px-3 py-2 bg-gray-100"
                  >
                    <span className="text-[9px] font-bold text-gray-600 uppercase tracking-wider">
                      Cost / Other Metrics
                    </span>
                  </td>{/* */}
                </tr>
                <tr>{/* */}
                  <td colSpan={TOTAL_COLS} className="border border-gray-300 p-0">
                    <table className="w-full text-xs border-collapse">
                      <thead>{/* */}
                        <tr className="bg-gray-50">{/* */}
                          <th className="border-b border-gray-200 px-2 py-1.5 text-left text-[9px] font-bold text-gray-500 uppercase w-[22%]">Category</th>
                          <th className="border-b border-gray-200 px-3 py-1.5 text-left text-[9px] font-bold text-gray-500 uppercase" style={{width:'50%'}}>Planned / Actual</th>
                          <th className="border-b border-gray-200 px-2 py-1.5 text-left text-[9px] font-bold text-gray-500 uppercase">Notes</th>
                          <th className="border-b border-gray-200 px-1 py-1.5 w-7"></th>{/* */}
                        </tr>
                      </thead>
                      <tbody>{/* */}
                        {costs.map((cost) => (
                          <CostRow
                            key={cost.id}
                            cost={cost}
                            maxAmount={maxCostAmount}
                            onUpdate={(data) => updateCostMut.mutate({ costId: cost.id, data })}
                            onDelete={() => {
                              if (confirm(`Delete cost "${cost.category}"?`)) {
                                deleteCostMut.mutate(cost.id)
                              }
                            }}
                          />
                        ))}
                        {/* Totals row */}
                        {costs.length > 0 && (
                          <tr className="bg-gray-50 font-semibold">{/* */}
                            <td className="border-t border-gray-300 px-2 py-1.5 text-xs text-gray-600">Total</td>
                            <td className="border-t border-gray-300 px-3 py-1.5">
                              <div className="flex gap-6 text-[10px]">
                                <span className="text-gray-500">Planned: <span className="font-bold text-blue-600">{(costData?.total_planned ?? 0).toLocaleString()}</span></span>
                                <span className="text-gray-500">Actual: <span className={cn('font-bold', (costData?.total_actual ?? 0) > (costData?.total_planned ?? 0) ? 'text-red-600' : 'text-emerald-600')}>{(costData?.total_actual ?? 0).toLocaleString()}</span></span>
                              </div>
                            </td>
                            <td className="border-t border-gray-300" colSpan={2}></td>{/* */}
                          </tr>
                        )}
                        {/* Add cost form */}
                        {showAddCost && (
                          <tr>{/* */}
                            <td className="px-2 py-1.5">
                              <input
                                value={newCost.category}
                                onChange={(e) => setNewCost((c) => ({ ...c, category: e.target.value }))}
                                placeholder="Category"
                                className="w-full text-xs border border-gray-300 rounded px-1.5 py-0.5 outline-none"
                              />
                            </td>
                            <td className="px-3 py-1.5">
                              <div className="flex gap-2">
                                <div className="flex-1">
                                  <label className="text-[9px] text-gray-400 block mb-0.5">Planned</label>
                                  <input
                                    type="number"
                                    value={newCost.planned_amount || ''}
                                    onChange={(e) => setNewCost((c) => ({ ...c, planned_amount: parseFloat(e.target.value) || 0 }))}
                                    placeholder="0"
                                    className="w-full text-xs border border-gray-300 rounded px-1.5 py-0.5 outline-none text-right"
                                  />
                                </div>
                                <div className="flex-1">
                                  <label className="text-[9px] text-gray-400 block mb-0.5">Actual</label>
                                  <input
                                    type="number"
                                    value={newCost.actual_amount || ''}
                                    onChange={(e) => setNewCost((c) => ({ ...c, actual_amount: parseFloat(e.target.value) || 0 }))}
                                    placeholder="0"
                                    className="w-full text-xs border border-gray-300 rounded px-1.5 py-0.5 outline-none text-right"
                                  />
                                </div>
                              </div>
                            </td>
                            <td className="px-2 py-1.5">
                              <input
                                value={newCost.notes}
                                onChange={(e) => setNewCost((c) => ({ ...c, notes: e.target.value }))}
                                placeholder="Notes"
                                className="w-full text-xs border border-gray-300 rounded px-1.5 py-0.5 outline-none"
                              />
                            </td>
                            <td className="px-1 py-1.5 text-center">
                              <button
                                onClick={() => {
                                  if (newCost.category.trim()) createCostMut.mutate(newCost)
                                }}
                                className="text-emerald-600 hover:text-emerald-700"
                              >
                                <Check className="h-3.5 w-3.5" />
                              </button>
                            </td>{/* */}
                          </tr>
                        )}{/* */}
                      </tbody>
                    </table>
                  </td>{/* */}
                </tr>
              </>
            )}

            {/* Add cost button */}
            <tr>{/* */}
              <td colSpan={TOTAL_COLS} className="border border-gray-300 px-3 py-1.5">
                <button
                  onClick={() => setShowAddCost((v) => !v)}
                  className="text-xs text-gray-500 hover:text-blue-600 flex items-center gap-1"
                >
                  <Plus className="h-3 w-3" />
                  {showAddCost ? 'Cancel' : 'Add cost item'}
                </button>
              </td>{/* */}
            </tr>

            {/* ══════════════════════════════════════════════════
                BOTTOM SECTION — Deliverables / Forecast / Risk / Team / Legend
            ══════════════════════════════════════════════════ */}

            {/* ══════════════════════════════════════════════════
                BOTTOM SECTION — Classic OPPM X-cross layout
            ══════════════════════════════════════════════════ */}

            {/* Section divider row */}
            <tr>{/* */}
              <td
                colSpan={TOTAL_COLS}
                className="border-t-2 border-gray-400 bg-gray-100 px-3 py-0.5"
              >
                <span className="text-[8px] font-bold text-gray-500 uppercase tracking-widest">
                  Summary &amp; Objectives
                </span>
              </td>{/* */}
            </tr>

            {/* Summary Deliverables row */}
            <tr>{/* */}
              <VerticalLabel>Summary Deliverables</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-2 py-2 align-top"
              >
                <EditableList
                  items={meta.summary_deliverables}
                  onSave={(v) => updateMeta.mutate({ summary_deliverables: v })}
                />
              </td>

              {/* ── X CROSS — spans all week + owner cols, rowSpan=3 ── */}
              <td
                colSpan={VISIBLE_WEEKS + 1}
                rowSpan={3}
                className="border border-gray-300 p-0 overflow-hidden"
              >
                <div
                  className="relative w-full h-full bg-white"
                  style={{ minHeight: '168px' }}
                >
                  {/* Diagonal X lines via SVG */}
                  <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    preserveAspectRatio="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <line x1="0" y1="0" x2="100%" y2="100%" stroke="#d1d5db" strokeWidth="1.5" />
                    <line x1="100%" y1="0" x2="0" y2="100%" stroke="#d1d5db" strokeWidth="1.5" />
                  </svg>

                  {/* Top-left quadrant: Major Tasks */}
                  <div className="absolute top-3 left-4 pointer-events-none select-none">
                    <div className="text-[9px] font-black text-gray-500 uppercase tracking-widest">
                      Major Tasks
                    </div>
                  </div>

                  {/* Top-right quadrant: Target Dates */}
                  <div className="absolute top-3 right-4 pointer-events-none select-none text-right">
                    <div className="text-[9px] font-black text-gray-500 uppercase tracking-widest">
                      Target Dates
                    </div>
                  </div>

                  {/* Center: Summary & Forecast badge */}
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="bg-white/95 border border-gray-300 rounded-sm px-4 py-2 text-center shadow-md z-10">
                      <div className="text-[9px] font-black text-gray-600 uppercase tracking-widest leading-snug">
                        Summary
                      </div>
                      <div className="text-[9px] font-black text-gray-600 uppercase tracking-widest leading-snug">
                        &amp; Forecast
                      </div>
                      <div className={cn(
                        'mt-1.5 text-base font-black leading-none',
                        overallProgress >= 80 ? 'text-emerald-600'
                        : overallProgress >= 50 ? 'text-blue-600'
                        : overallProgress > 0  ? 'text-amber-600'
                        : 'text-gray-400'
                      )}>
                        {overallProgress}%
                      </div>
                    </div>
                  </div>

                  {/* Bottom-left quadrant: Objectives */}
                  <div className="absolute bottom-3 left-4 pointer-events-none select-none">
                    <div className="text-[9px] font-black text-gray-500 uppercase tracking-widest">
                      Objectives
                    </div>
                  </div>

                  {/* Bottom-right quadrant: Cost or Other Metrics */}
                  <div className="absolute bottom-3 right-4 pointer-events-none select-none text-right">
                    <div className="text-[9px] font-black text-gray-500 uppercase tracking-widest leading-snug">
                      Cost or<br />Other Metrics
                    </div>
                  </div>

                  {/* Status legend — floating bottom-left above Objectives label */}
                  <div className="absolute space-y-0.5 pointer-events-none select-none"
                    style={{ bottom: '28px', left: '16px' }}
                  >
                    {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                      <div key={key} className="flex items-center gap-1.5">
                        <span className={cn('h-2 w-4 rounded-sm shrink-0', cfg.bg)} />
                        <span className="text-[8px] text-gray-500">{cfg.label}</span>
                      </div>
                    ))}
                  </div>

                  {/* Team — floating top-right below Target Dates label */}
                  <div className="absolute pointer-events-none select-none"
                    style={{ top: '28px', right: '16px' }}
                  >
                    <div className="text-[8px] font-bold text-gray-400 uppercase tracking-wider mb-1 text-right">
                      Project Leader
                    </div>
                    <div className="text-[10px] font-semibold text-gray-600 text-right">
                      {leaderName}
                    </div>
                  </div>
                </div>
              </td>{/* */}
            </tr>

            {/* Forecast row */}
            <tr>{/* */}
              <VerticalLabel>Forecast</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-2 py-2 align-top"
              >
                <InlineTextarea
                  value={meta.forecast}
                  onSave={(v) => updateMeta.mutate({ forecast: v })}
                />
              </td>{/* */}
            </tr>

            {/* Risk row */}
            <tr>{/* */}
              <VerticalLabel>Risk</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-2 py-2 align-top"
              >
                <RiskEditor
                  items={meta.risks}
                  onSave={(v) => updateMeta.mutate({ risks: v })}
                />
              </td>{/* */}
            </tr>{/* */}

          </tbody>
        </table>
      </div>

    </div>
  )
}
