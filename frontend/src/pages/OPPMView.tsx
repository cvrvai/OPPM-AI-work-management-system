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
const SHEET_COLUMNS = Array.from({ length: 14 }, (_, index) => OBJ_LETTERS[index])
const SHEET_COLUMN_HEADER_CELL = 'sticky top-0 z-20 border border-slate-300 bg-slate-100 px-2 py-1 text-center text-[10px] font-medium text-slate-500'
const SHEET_ROW_NUMBER_CELL = 'sticky left-0 z-10 border border-slate-300 bg-slate-100 px-1 py-1.5 text-center text-[10px] font-medium text-slate-500 align-top'
const SHEET_CELL = 'border border-slate-300 bg-white px-2 py-2 align-top'
const SHEET_LABEL = 'text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-400'

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  // planned = outlined blue (scheduled but not started — real OPPM open circle)
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
        // empty = faint outline (not scheduled); planned = outlined blue (scheduled)
        cfg ? cfg.bg : 'border-[1.5px] border-gray-200 bg-transparent'
      )}
    />
  )
}

// ─────────────────────────────────────────────────────────────
// OwnerSelect — custom dropdown replacing native <select>
// so the browser's ugly styled list never appears in the table
// ─────────────────────────────────────────────────────────────
function OwnerSelect({
  value,
  members,
  onChange,
}: {
  value: string
  members: { id: string; display_name: string | null; email: string }[]
  onChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = members.find((m) => m.id === value)
  const label = selected ? (selected.display_name || selected.email.split('@')[0]) : '—'

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-center gap-0.5 text-[10px] text-gray-600 hover:text-gray-900 transition-colors"
        title="Assign owner"
      >
        <span className="truncate max-w-[72px]">{label}</span>
        <svg className="h-2.5 w-2.5 shrink-0 text-gray-400" viewBox="0 0 12 12" fill="none">
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-0.5 z-50 min-w-[130px] rounded-lg border border-gray-200 bg-white shadow-lg py-1 text-left">
          <button
            type="button"
            className="w-full px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-50 text-left"
            onClick={() => { onChange(''); setOpen(false) }}
          >
            — Unassign
          </button>
          {members.map((m) => (
            <button
              key={m.id}
              type="button"
              className={cn(
                'w-full px-3 py-1.5 text-xs text-left hover:bg-blue-50 hover:text-blue-700 transition-colors',
                m.id === value ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'
              )}
              onClick={() => { onChange(m.id); setOpen(false) }}
            >
              {m.display_name || m.email.split('@')[0]}
            </button>
          ))}
        </div>
      )}
    </div>
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
  emptyMessage = 'Click to add notes...',
}: {
  value: string
  onSave: (value: string) => void
  emptyMessage?: string
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
        <p className="text-xs text-gray-300 italic">{emptyMessage}</p>
      )}
      <div className="text-[10px] text-transparent group-hover:text-blue-400 mt-0.5 transition-colors">
        ✎ click to edit
      </div>
    </div>
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
      {/* Description */}
      <td className="border-b border-gray-200 px-2 py-2 align-middle">
        <InlineEdit
          value={cost.description}
          onSave={(v) => onUpdate({ description: v })}
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
  const [newCost, setNewCost] = useState({ category: '', planned_amount: 0, actual_amount: 0, description: '' })

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

  const { data: wsMembers = [] } = useQuery<{ id: string; user_id: string; display_name: string | null; email: string }[]>({
    queryKey: ['ws-members', ws?.id],
    queryFn: () => api.get(`${wsPath}/members`),
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
    mutationFn: (data: { category: string; planned_amount: number; actual_amount: number; description: string }) =>
      api.post(`${wsPath}/projects/${id}/oppm/costs`, { ...data, project_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oppm-costs', id] })
      setShowAddCost(false)
      setNewCost({ category: '', planned_amount: 0, actual_amount: 0, description: '' })
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

  const rawMeta = (project?.metadata as OPPMMetadata) ?? {}
  let normalizedRisks: RiskItem[]
  if (rawMeta.risks?.length) {
    normalizedRisks = (rawMeta.risks as (string | RiskItem)[]).map((item) =>
      typeof item === 'string' ? { text: item, rag: 'green' as const } : item
    )
  } else {
    normalizedRisks = [{ text: '', rag: 'green' }, { text: '', rag: 'green' }, { text: '', rag: 'green' }, { text: '', rag: 'green' }]
  }

  let normalizedForecast = ''
  if (typeof rawMeta.forecast === 'string') {
    normalizedForecast = rawMeta.forecast
  } else if (Array.isArray(rawMeta.forecast) && rawMeta.forecast.length) {
    normalizedForecast = rawMeta.forecast.filter(Boolean).join('\n')
  }

  const meta: NormalizedMeta = {
    deliverable_output: rawMeta.deliverable_output ?? '',
    summary_deliverables: rawMeta.summary_deliverables?.length ? rawMeta.summary_deliverables : ['', '', '', ''],
    forecast: normalizedForecast,
    risks: normalizedRisks,
  }

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

  // Calculate progress per objective using ALL timeline entries (not just visible weeks)
  const calcProgress = useCallback(
    (objId: string): number => {
      const objTimeline = timelineMap[objId]
      if (!objTimeline) return 0
      const all = Object.values(objTimeline)
      if (all.length === 0) return 0
      const completed = all.filter((s) => s === 'completed').length
      return Math.round((completed / all.length) * 100)
    },
    [timelineMap]
  )

  const overallProgress = useMemo(() => {
    const objs = objectives ?? []
    if (objs.length === 0) return 0
    let total = 0
    let completedCells = 0
    for (const obj of objs) {
      const objTimeline = timelineMap[obj.id]
      if (!objTimeline) continue
      const entries = Object.values(objTimeline)
      total += entries.length
      completedCells += entries.filter((s) => s === 'completed').length
    }
    if (total === 0) return 0
    return Math.round((completedCells / total) * 100)
  }, [objectives, timelineMap])

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

  const leaderName = user?.full_name ?? user?.user_metadata?.full_name ?? user?.email?.split('@')[0] ?? 'Project Leader'
  const totalTaskCount = useMemo(
    () => (objectives ?? []).reduce((sum, objective) => sum + (objective.tasks?.length ?? 0), 0),
    [objectives]
  )
  const atRiskCount = useMemo(
    () => (timelineEntries ?? []).filter((entry) => entry.status === 'at_risk').length,
    [timelineEntries]
  )
  const blockedCount = useMemo(
    () => (timelineEntries ?? []).filter((entry) => entry.status === 'blocked').length,
    [timelineEntries]
  )
  const visibleWindowLabel = useMemo(() => {
    const firstWeek = weeks[0]
    const lastWeek = weeks[weeks.length - 1]
    return `${format(firstWeek.start, 'MMM d')} - ${format(lastWeek.end, 'MMM d, yyyy')}`
  }, [weeks])

  const maxCostAmount = useMemo(
    () => Math.max(...(costData?.items ?? []).flatMap((c) => [c.planned_amount, c.actual_amount]), 1),
    [costData],
  )

  // ── Loading / Error states ──────────────────────────────────
  // Only block on project (used in header); objectives use skeleton rows so
  // the header renders instantly (project is usually cached from ProjectDetail).
  if (loadingProject) {
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
  const deliverableCount = meta.summary_deliverables.filter((item) => item.trim()).length
  const recordedRiskCount = meta.risks.filter((item) => item.text.trim()).length
  const costVariance = (costData?.total_actual ?? 0) - (costData?.total_planned ?? 0)
  const visibleObjectiveRows = Math.max(objs.length, MIN_OBJECTIVE_ROWS)
  const addObjectiveRowNumber = 7 + visibleObjectiveRows
  const peopleRowNumber = addObjectiveRowNumber + 1
  const summaryRowNumber = peopleRowNumber + 1
  const forecastRowNumber = summaryRowNumber + 1
  const riskRowNumber = summaryRowNumber + 2
  const costHeaderRowNumber = summaryRowNumber + 3
  const costBodyRowNumber = summaryRowNumber + 4

  // ── Render ────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
        <Link
          to={`/projects/${id}`}
          className="rounded-lg border border-slate-300 bg-white p-2 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">OPPM Spreadsheet View</p>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-lg font-semibold text-slate-900">{p.title}</h1>
            <span className={cn('rounded-md px-2 py-0.5 text-[10px] font-semibold capitalize', getStatusColor(p.status))}>
              {p.status.replace('_', ' ')}
            </span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setWeekOffset((offset) => offset - 1)}
            className="rounded-lg border border-slate-300 bg-white p-2 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
            title="Previous window"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Visible Window</p>
            <p className="text-xs font-medium text-slate-700">{visibleWindowLabel}</p>
          </div>
          <button
            onClick={() => setWeekOffset((offset) => offset + 1)}
            className="rounded-lg border border-slate-300 bg-white p-2 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
            title="Next window"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-300 bg-white shadow-sm">
        <div className="min-w-[1490px] border-b border-slate-300 bg-slate-50 px-3 py-2">
          <div className="grid grid-cols-[76px_minmax(0,1fr)] items-center gap-2">
            <div className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-500">A1</div>
            <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-[11px] text-slate-500">
              <span className="font-semibold text-slate-400">fx</span>
              <span className="truncate">{p.title} OPPM sheet</span>
            </div>
          </div>
        </div>
        <div className="flex min-w-[1500px] items-start gap-2 bg-slate-50 p-2.5">
          <table className="w-[1174px] shrink-0 border-collapse table-fixed bg-white text-xs shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
            <colgroup>
              <col style={{ width: '40px' }} />
              <col style={{ width: '78px' }} />
              <col style={{ width: '120px' }} />
              <col style={{ width: '120px' }} />
              <col style={{ width: '120px' }} />
              <col style={{ width: '120px' }} />
              {Array.from({ length: VISIBLE_WEEKS }).map((_, index) => (
                <col key={index} style={{ width: '58px' }} />
              ))}
              <col style={{ width: '112px' }} />
            </colgroup>
            <thead>
              <tr>
                <th className={cn(SHEET_COLUMN_HEADER_CELL, 'left-0 z-30')} />
                {SHEET_COLUMNS.map((letter) => (
                  <th key={letter} className={SHEET_COLUMN_HEADER_CELL}>{letter}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>1</td>
                <td colSpan={6} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Project Leader</p>
                  <div className="mt-1 text-sm font-semibold text-slate-900">{leaderName}</div>
                </td>
                <td colSpan={8} className={SHEET_CELL}>
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className={SHEET_LABEL}>Project Name</p>
                      <div className="mt-1 truncate text-sm font-semibold text-slate-900">{p.title}</div>
                    </div>
                    <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600">
                      OPPM Sheet
                    </div>
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>2</td>
                <td colSpan={9} className={SHEET_CELL}>
                      <p className={SHEET_LABEL}>Project Objective</p>
                  <p className="mt-1 text-sm leading-6 text-slate-700">
                    {p.description || p.objective_summary || 'Capture the project objective here so the execution sheet stays aligned to the core outcome.'}
                  </p>
                </td>
                <td colSpan={5} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Project Complete By</p>
                  <div className="mt-1 text-sm font-semibold text-slate-900">
                    {p.deadline ? formatDate(p.deadline) : 'Not set'}
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>3</td>
                <td colSpan={9} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Deliverable Output</p>
                  <div className="mt-1">
                    <InlineTextarea
                      value={meta.deliverable_output}
                      onSave={(value) => updateMeta.mutate({ deliverable_output: value })}
                      emptyMessage="Click to add deliverable output..."
                    />
                  </div>
                </td>
                <td colSpan={5} className={SHEET_CELL}>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className={SHEET_LABEL}>Start Date</p>
                      <div className="mt-1 text-sm font-semibold text-slate-900">
                        {p.start_date ? formatDate(p.start_date) : 'Not set'}
                      </div>
                    </div>
                    <div>
                      <p className={SHEET_LABEL}>Window</p>
                      <div className="mt-1 text-sm font-semibold text-slate-900">{visibleWindowLabel}</div>
                    </div>
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>4</td>
                <td colSpan={4} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Overall Progress</p>
                  <div className="mt-1 flex items-end justify-between gap-4">
                    <span className={cn(
                      'text-2xl font-black',
                      overallProgress >= 80 ? 'text-emerald-600' : overallProgress >= 50 ? 'text-blue-600' : overallProgress > 0 ? 'text-amber-600' : 'text-slate-400'
                    )}>
                      {overallProgress}%
                    </span>
                    <span className="text-[11px] text-slate-500">Tracked from weekly status dots</span>
                  </div>
                </td>
                <td colSpan={2} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Objectives</p>
                  <div className="mt-1 text-lg font-bold text-slate-900">{objs.length}</div>
                </td>
                <td colSpan={2} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Linked Tasks</p>
                  <div className="mt-1 text-lg font-bold text-slate-900">{totalTaskCount}</div>
                </td>
                <td colSpan={2} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Deliverables</p>
                  <div className="mt-1 text-lg font-bold text-slate-900">{deliverableCount}</div>
                </td>
                <td colSpan={2} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Risks</p>
                  <div className="mt-1 text-lg font-bold text-slate-900">{recordedRiskCount}</div>
                </td>
                <td colSpan={2} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Cost Variance</p>
                  <div className={cn('mt-1 text-lg font-bold', costVariance > 0 ? 'text-red-600' : costVariance < 0 ? 'text-emerald-600' : 'text-slate-900')}>
                    {costVariance === 0 ? '0' : `${costVariance > 0 ? '+' : '-'}${Math.abs(costVariance).toLocaleString()}`}
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>5</td>
                <td colSpan={14} className="border border-slate-300 bg-slate-100 px-3 py-1.5 align-middle">
                  <div className="flex items-center justify-between gap-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    <span>Execution Sheet</span>
                    <span>{p.objective_summary || 'Use the rows below to keep the OPPM visible in one page.'}</span>
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>6</td>
                <td className="border border-slate-300 bg-slate-100 px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Sub Objective</td>
                <td colSpan={4} className="border border-slate-300 bg-slate-100 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Major Tasks (Deadline)</td>
                {weeks.map((week, index) => (
                  <td
                    key={week.isoDate}
                    className={cn(
                      'border border-slate-300 px-1 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500',
                      index === currentWeekIdx ? 'bg-blue-50 text-blue-700' : 'bg-slate-100'
                    )}
                  >
                    <div>W{week.weekNum}</div>
                    <div className="mt-0.5 text-[9px] font-normal normal-case tracking-normal text-slate-400">{week.label}</div>
                  </td>
                ))}
                <td className="border border-slate-300 bg-slate-100 px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Owner / Priority</td>
              </tr>

              {loadingObjectives ? Array.from({ length: 4 }).map((_, index) => (
                <tr key={`oppm-skeleton-${index}`}>
                  <td className={SHEET_ROW_NUMBER_CELL}>{7 + index}</td>
                  <td className={SHEET_CELL}><div className="mx-auto h-4 w-4 rounded-full bg-slate-200 animate-pulse" /></td>
                  <td colSpan={4} className={SHEET_CELL}><div className="h-4 w-3/4 rounded bg-slate-200 animate-pulse" /></td>
                  {Array.from({ length: VISIBLE_WEEKS }).map((__, weekIndex) => (
                    <td key={weekIndex} className={cn(SHEET_CELL, 'px-1 py-3 text-center')}><div className="mx-auto h-4 w-4 rounded-full bg-slate-200 animate-pulse" /></td>
                  ))}
                  <td className={SHEET_CELL}><div className="mx-auto h-4 w-16 rounded bg-slate-200 animate-pulse" /></td>
                </tr>
              )) : (
                <>
                  {objs.map((obj, objIndex) => {
                    const objProgress = calcProgress(obj.id)
                    const linkedTasks = obj.tasks ?? []
                    const rowStatuses = Object.values(timelineMap[obj.id] ?? {})
                    const summaryStatus: string | undefined =
                      rowStatuses.length === 0 ? undefined
                      : rowStatuses.every((status) => status === 'completed') ? 'completed'
                      : rowStatuses.includes('blocked') ? 'blocked'
                      : rowStatuses.includes('at_risk') ? 'at_risk'
                      : rowStatuses.includes('in_progress') ? 'in_progress'
                      : 'planned'

                    return (
                      <tr key={obj.id}>
                        <td className={SHEET_ROW_NUMBER_CELL}>{7 + objIndex}</td>
                        <td className={cn(SHEET_CELL, 'px-1 py-3 text-center')}>
                          <div className="flex flex-col items-center gap-1.5">
                            <StatusDot status={summaryStatus} />
                            <span className="text-[10px] font-black text-slate-500">{OBJ_LETTERS[objIndex % 26]}</span>
                          </div>
                        </td>
                        <td colSpan={4} className={cn(SHEET_CELL, 'px-3 py-3')}>
                          <div className="space-y-2">
                            <div className="flex items-start gap-2">
                              <span className="mt-0.5 text-[11px] font-bold text-slate-400">{objIndex + 1}.</span>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-start gap-2">
                                  <InlineEdit
                                    value={obj.title}
                                    onSave={(value) => updateObjective.mutate({ objId: obj.id, data: { title: value } })}
                                    className="text-[13px] font-semibold text-slate-900"
                                  />
                                  <button
                                    onClick={() => {
                                      if (confirm(`Delete objective "${obj.title}"?`)) {
                                        deleteObjective.mutate(obj.id)
                                      }
                                    }}
                                    className="text-gray-300 transition-colors hover:text-red-500"
                                    title="Delete objective"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                                <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                                  <span>{linkedTasks.length > 0 ? `${linkedTasks.length} linked task${linkedTasks.length === 1 ? '' : 's'}` : 'No linked tasks yet'}</span>
                                  <span className={cn(
                                    'font-semibold',
                                    objProgress >= 80 ? 'text-emerald-700' : objProgress >= 50 ? 'text-blue-700' : objProgress > 0 ? 'text-amber-700' : 'text-slate-400'
                                  )}>
                                    {objProgress > 0 ? `${objProgress}% complete` : 'Not started'}
                                  </span>
                                </div>
                                {linkedTasks.length > 0 && (
                                  <div className="mt-1 text-[11px] leading-5 text-slate-500">
                                    {linkedTasks.slice(0, 3).map((task) => task.title).join(' • ')}
                                    {linkedTasks.length > 3 ? ` • +${linkedTasks.length - 3} more` : ''}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                        {weeks.map((week, weekIndex) => {
                          const status = timelineMap[obj.id]?.[week.isoDate]
                          return (
                            <td
                              key={week.isoDate}
                              className={cn(SHEET_CELL, 'px-1 py-3 text-center', weekIndex === currentWeekIdx && 'bg-blue-50/50')}
                            >
                              <StatusDot status={status} onClick={() => handleDotClickFull(obj.id, week.isoDate)} />
                            </td>
                          )
                        })}
                        <td className={cn(SHEET_CELL, 'px-2 py-3 text-center')}>
                          <OwnerSelect
                            value={obj.owner_id ?? ''}
                            members={wsMembers}
                            onChange={(ownerId) => updateObjective.mutate({ objId: obj.id, data: { owner_id: ownerId || null } })}
                          />
                        </td>
                      </tr>
                    )
                  })}

                  {Array.from({ length: Math.max(MIN_OBJECTIVE_ROWS - objs.length, 0) }).map((_, fillerIndex) => (
                    <tr key={`oppm-filler-${fillerIndex}`}>
                      <td className={SHEET_ROW_NUMBER_CELL}>{7 + objs.length + fillerIndex}</td>
                      <td className={cn(SHEET_CELL, 'px-1 py-3')} />
                      <td colSpan={4} className={SHEET_CELL}>
                        {objs.length === 0 && fillerIndex === 0 ? (
                          <span className="text-[11px] italic text-slate-300">Add the first objective below to begin the sheet.</span>
                        ) : (
                          <div className="h-6" />
                        )}
                      </td>
                      {Array.from({ length: VISIBLE_WEEKS }).map((__, weekIndex) => (
                        <td key={weekIndex} className={cn(SHEET_CELL, 'px-1 py-3 text-center', weekIndex === currentWeekIdx && 'bg-blue-50/50')} />
                      ))}
                      <td className={SHEET_CELL} />
                    </tr>
                  ))}
                </>
              )}

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{addObjectiveRowNumber}</td>
                <td className={cn(SHEET_CELL, 'px-1 py-3 text-center')}>
                  <Plus className="mx-auto h-4 w-4 text-slate-400" />
                </td>
                <td colSpan={13} className={SHEET_CELL}>
                  <div className="flex items-center gap-3">
                    <input
                      value={newObjTitle}
                      onChange={(e) => setNewObjTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && newObjTitle.trim()) {
                          createObjective.mutate(newObjTitle.trim())
                        }
                      }}
                      placeholder="Add objective to the sheet"
                      className="flex-1 border-none bg-transparent px-0 py-1 text-sm text-slate-700 outline-none placeholder:text-slate-300"
                    />
                    <button
                      onClick={() => createObjective.mutate(newObjTitle.trim())}
                      disabled={createObjective.isPending || !newObjTitle.trim()}
                      className="inline-flex items-center justify-center rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                      {createObjective.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Add objective'}
                    </button>
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{peopleRowNumber}</td>
                <td colSpan={14} className="border border-slate-300 bg-slate-100 px-3 py-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  # People working on the project: {wsMembers.length}
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{summaryRowNumber}</td>
                <td colSpan={8} rowSpan={3} className={cn(SHEET_CELL, 'p-0')}>
                  <div className="relative min-h-[220px] overflow-hidden bg-white">
                    <svg className="absolute inset-0 h-full w-full pointer-events-none" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                      <line x1="0" y1="0" x2="100%" y2="100%" stroke="#cbd5e1" strokeWidth="1.25" />
                      <line x1="100%" y1="0" x2="0" y2="100%" stroke="#cbd5e1" strokeWidth="1.25" />
                    </svg>
                    <div className="absolute left-6 top-5 text-xs font-semibold text-slate-500">Major Tasks</div>
                    <div className="absolute right-6 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-500">Target Dates</div>
                    <div className="absolute bottom-10 left-6 text-xs font-semibold text-slate-500">Sub Objectives</div>
                    <div className="absolute bottom-10 right-6 text-xs font-semibold text-slate-500">Costs</div>
                    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-xs font-semibold text-slate-500">Summary &amp; Forecast</div>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="rounded-lg border border-slate-300 bg-white/95 px-5 py-4 text-center shadow-sm">
                        <Target className="mx-auto h-5 w-5 text-blue-600" />
                        <div className="mt-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Sheet Snapshot</div>
                        <div className={cn(
                          'mt-2 text-3xl font-black',
                          overallProgress >= 80 ? 'text-emerald-600' : overallProgress >= 50 ? 'text-blue-600' : overallProgress > 0 ? 'text-amber-600' : 'text-slate-400'
                        )}>
                          {overallProgress}%
                        </div>
                        <div className="mt-2 text-[11px] text-slate-500">{objs.length} objective{objs.length === 1 ? '' : 's'} · {totalTaskCount} linked task{totalTaskCount === 1 ? '' : 's'}</div>
                      </div>
                    </div>
                  </div>
                </td>
                <td colSpan={6} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Summary Deliverables</p>
                  <div className="mt-2">
                    <EditableList
                      items={meta.summary_deliverables}
                      onSave={(items) => updateMeta.mutate({ summary_deliverables: items })}
                    />
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{forecastRowNumber}</td>
                <td colSpan={6} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Forecast</p>
                  <div className="mt-2">
                    <InlineTextarea
                      value={meta.forecast}
                      onSave={(value) => updateMeta.mutate({ forecast: value })}
                      emptyMessage="Click to add summary and forecast..."
                    />
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{riskRowNumber}</td>
                <td colSpan={6} className={SHEET_CELL}>
                  <p className={SHEET_LABEL}>Risk</p>
                  <div className="mt-2">
                    <RiskEditor
                      items={meta.risks}
                      onSave={(items) => updateMeta.mutate({ risks: items })}
                    />
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{costHeaderRowNumber}</td>
                <td colSpan={14} className="border border-slate-300 bg-slate-100 px-3 py-1.5 align-middle">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Cost / Other Metrics</span>
                    <button
                      onClick={() => setShowAddCost((value) => !value)}
                      className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      {showAddCost ? 'Cancel' : 'Add cost item'}
                    </button>
                  </div>
                </td>
              </tr>

              <tr>
                <td className={SHEET_ROW_NUMBER_CELL}>{costBodyRowNumber}</td>
                <td colSpan={14} className="border border-slate-300 bg-white p-0 align-top">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50">
                        <th className="border-b border-slate-200 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500" style={{ width: '22%' }}>Category</th>
                        <th className="border-b border-slate-200 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500" style={{ width: '50%' }}>Planned / Actual</th>
                        <th className="border-b border-slate-200 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Notes</th>
                        <th className="border-b border-slate-200 px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500" />
                      </tr>
                    </thead>
                    <tbody>
                      {costs.length === 0 && !showAddCost && (
                        <tr>
                          <td colSpan={4} className="px-4 py-8 text-center text-slate-400">No cost items yet. Add the first row to track planned versus actual values.</td>
                        </tr>
                      )}
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
                      {showAddCost && (
                        <tr>
                          <td className="px-3 py-2 align-top">
                            <input
                              value={newCost.category}
                              onChange={(e) => setNewCost((cost) => ({ ...cost, category: e.target.value }))}
                              placeholder="Category"
                              className="w-full rounded border border-gray-300 px-2 py-1 text-xs outline-none focus:border-blue-500"
                            />
                          </td>
                          <td className="px-3 py-2 align-top">
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <label className="mb-1 block text-[10px] font-medium text-gray-400">Planned</label>
                                <input
                                  type="number"
                                  value={newCost.planned_amount || ''}
                                  onChange={(e) => setNewCost((cost) => ({ ...cost, planned_amount: parseFloat(e.target.value) || 0 }))}
                                  placeholder="0"
                                  className="w-full rounded border border-gray-300 px-2 py-1 text-right text-xs outline-none focus:border-blue-500"
                                />
                              </div>
                              <div>
                                <label className="mb-1 block text-[10px] font-medium text-gray-400">Actual</label>
                                <input
                                  type="number"
                                  value={newCost.actual_amount || ''}
                                  onChange={(e) => setNewCost((cost) => ({ ...cost, actual_amount: parseFloat(e.target.value) || 0 }))}
                                  placeholder="0"
                                  className="w-full rounded border border-gray-300 px-2 py-1 text-right text-xs outline-none focus:border-blue-500"
                                />
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-2 align-top">
                            <input
                              value={newCost.description}
                              onChange={(e) => setNewCost((cost) => ({ ...cost, description: e.target.value }))}
                              placeholder="Description"
                              className="w-full rounded border border-gray-300 px-2 py-1 text-xs outline-none focus:border-blue-500"
                            />
                          </td>
                          <td className="px-2 py-2 align-top text-center">
                            <button
                              onClick={() => {
                                if (newCost.category.trim()) {
                                  createCostMut.mutate(newCost)
                                }
                              }}
                              className="text-emerald-600 transition-colors hover:text-emerald-700"
                              title="Save cost item"
                            >
                              <Check className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </td>
              </tr>
            </tbody>
          </table>

          <div className="w-[300px] shrink-0 space-y-4">
            <table className="w-full border-collapse table-fixed bg-white text-xs shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
              <colgroup>
                <col style={{ width: '40px' }} />
                <col style={{ width: '86px' }} />
                <col style={{ width: '86px' }} />
                <col style={{ width: '86px' }} />
              </colgroup>
              <thead>
                <tr>
                  <th className={cn(SHEET_COLUMN_HEADER_CELL, 'left-0 z-30')} />
                  <th className={SHEET_COLUMN_HEADER_CELL}>A</th>
                  <th className={SHEET_COLUMN_HEADER_CELL}>B</th>
                  <th className={SHEET_COLUMN_HEADER_CELL}>C</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>1</td>
                  <td colSpan={3} className={SHEET_CELL}>
                    <p className={SHEET_LABEL}>Priority</p>
                  </td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>2</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-center text-[11px] font-semibold text-slate-900">A</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-center text-[11px] font-semibold text-slate-900">B</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-center text-[11px] font-semibold text-slate-900">C</td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>3</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-[11px] text-slate-600">Primary / Owner</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-[11px] text-slate-600">Primary Helper</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-[11px] text-slate-600">Secondary Helper</td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>4</td>
                  <td colSpan={3} className={SHEET_CELL}>
                    <p className={SHEET_LABEL}>Project Identity Symbol</p>
                  </td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>5</td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-center">
                    <StatusDot status="planned" />
                    <div className="mt-1 text-[11px] text-slate-600">Start</div>
                  </td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-center">
                    <StatusDot status="in_progress" />
                    <div className="mt-1 text-[11px] text-slate-600">In Progress</div>
                  </td>
                  <td className="border border-slate-300 bg-white px-2 py-2 text-center">
                    <StatusDot status="completed" />
                    <div className="mt-1 text-[11px] text-slate-600">Complete</div>
                  </td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>6</td>
                  <td className="border border-slate-300 bg-emerald-500/15 px-2 py-2 text-center text-[11px] font-medium text-emerald-700">Good</td>
                  <td className="border border-slate-300 bg-amber-400/20 px-2 py-2 text-center text-[11px] font-medium text-amber-700">Average</td>
                  <td className="border border-slate-300 bg-red-500/15 px-2 py-2 text-center text-[11px] font-medium text-red-700">Bad</td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>7</td>
                  <td colSpan={3} className={SHEET_CELL}>
                    <p className={SHEET_LABEL}>Current Sheet Window</p>
                    <div className="mt-1 text-sm font-semibold text-slate-900">{visibleWindowLabel}</div>
                  </td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>8</td>
                  <td colSpan={3} className={SHEET_CELL}>
                    <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                      <span>Timeline attention</span>
                      <span className="text-right font-semibold text-slate-900">{atRiskCount + blockedCount}</span>
                      <span>Planned budget</span>
                      <span className="text-right font-semibold text-slate-900">{(costData?.total_planned ?? 0).toLocaleString()}</span>
                      <span>Actual budget</span>
                      <span className="text-right font-semibold text-slate-900">{(costData?.total_actual ?? 0).toLocaleString()}</span>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td className={SHEET_ROW_NUMBER_CELL}>9</td>
                  <td colSpan={3} className={SHEET_CELL}>
                    <p className={SHEET_LABEL}>Active Team</p>
                    <div className="mt-2 space-y-1 text-[11px] text-slate-600">
                      <div className="flex items-center justify-between gap-3">
                        <span>Project Leader</span>
                        <span className="truncate font-medium text-slate-900">{leaderName}</span>
                      </div>
                      {wsMembers.slice(0, 4).map((member, index) => (
                        <div key={member.id} className="flex items-center justify-between gap-3">
                          <span>Member {index + 1}</span>
                          <span className="truncate">{member.display_name || member.email.split('@')[0]}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
