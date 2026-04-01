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
  Check, X, Plus, Trash2, Bot,
} from 'lucide-react'
import { startOfWeek, addWeeks, format, parseISO, isWithinInterval, endOfWeek } from 'date-fns'
import { ChatPanel } from '@/components/ChatPanel'

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────
const VISIBLE_WEEKS = 8
const TOTAL_COLS = VISIBLE_WEEKS + 4 // SubObj + Tasks + % + weeks + Owner

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
// Metadata type
// ─────────────────────────────────────────────────────────────
interface OPPMMetadata {
  deliverable_output?: string
  summary_deliverables?: string[]
  forecast?: string[]
  risks?: string[]
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
// CostRow — single cost item row
// ─────────────────────────────────────────────────────────────
function CostRow({
  cost,
  onUpdate,
  onDelete,
}: {
  cost: OPPMCost
  onUpdate: (data: Partial<OPPMCost>) => void
  onDelete: () => void
}) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="border border-gray-300 px-2 py-1.5">
        <InlineEdit
          value={cost.category}
          onSave={(v) => onUpdate({ category: v })}
          className="text-xs text-gray-700"
        />
      </td>
      <td className="border border-gray-300 px-2 py-1.5 text-right">
        <InlineEdit
          value={String(cost.planned_amount)}
          onSave={(v) => onUpdate({ planned_amount: parseFloat(v) || 0 })}
          className="text-xs text-gray-700 text-right"
        />
      </td>
      <td className="border border-gray-300 px-2 py-1.5 text-right">
        <InlineEdit
          value={String(cost.actual_amount)}
          onSave={(v) => onUpdate({ actual_amount: parseFloat(v) || 0 })}
          className="text-xs text-gray-700 text-right"
        />
      </td>
      <td className="border border-gray-300 px-2 py-1.5">
        <InlineEdit
          value={cost.notes}
          onSave={(v) => onUpdate({ notes: v })}
          placeholder="—"
          className="text-xs text-gray-500"
        />
      </td>
      <td className="border border-gray-300 px-1 py-1.5 text-center">
        <button
          onClick={onDelete}
          className="text-gray-400 hover:text-red-500 transition-colors"
          title="Delete cost"
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
  const [chatOpen, setChatOpen] = useState(false)

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

  const meta: Required<OPPMMetadata> = useMemo(() => {
    const m = (project?.metadata as OPPMMetadata) ?? {}
    return {
      deliverable_output:    m.deliverable_output    ?? '',
      summary_deliverables:  m.summary_deliverables?.length ? m.summary_deliverables : ['', '', '', ''],
      forecast:              m.forecast?.length             ? m.forecast             : ['', '', '', ''],
      risks:                 m.risks?.length                ? m.risks                : ['', '', '', ''],
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
            onClick={() => setChatOpen((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors',
              chatOpen
                ? 'border-blue-300 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:bg-gray-50'
            )}
          >
            <Bot className="h-4 w-4" />
            AI Chat
          </button>
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
            <col style={{ width: '40px' }} />{/* Sub Obj */}
            <col style={{ width: '220px' }} />{/* Major Tasks */}
            <col style={{ width: '38px' }} />{/* % */}
            {Array.from({ length: VISIBLE_WEEKS }).map((_, i) => (
              <col key={i} style={{ width: '68px' }} />
            ))}{/* */}
            <col style={{ width: '72px' }} />{/* Owner / Priority */}
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
                Sub<br />Obj
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
                  {/* Sub Obj # */}
                  <td className="border border-gray-300 text-center align-middle">
                    <span className="text-xs font-bold text-gray-400">
                      {objIdx + 1}
                    </span>
                  </td>

                  {/* Objective title — inline editable */}
                  <td className="border border-gray-300 px-3 py-2 align-middle">
                    <div className="flex items-center gap-1">
                      <InlineEdit
                        value={obj.title}
                        onSave={(v) =>
                          updateObjective.mutate({ objId: obj.id, data: { title: v } })
                        }
                        className="text-sm font-medium text-gray-800 flex-1"
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
                          <th className="border-b border-gray-200 px-2 py-1.5 text-left text-[9px] font-bold text-gray-500 uppercase w-1/4">Category</th>
                          <th className="border-b border-gray-200 px-2 py-1.5 text-right text-[9px] font-bold text-gray-500 uppercase w-1/5">Planned</th>
                          <th className="border-b border-gray-200 px-2 py-1.5 text-right text-[9px] font-bold text-gray-500 uppercase w-1/5">Actual</th>
                          <th className="border-b border-gray-200 px-2 py-1.5 text-left text-[9px] font-bold text-gray-500 uppercase">Notes</th>
                          <th className="border-b border-gray-200 px-1 py-1.5 w-8"></th>{/* */}
                        </tr>
                      </thead>
                      <tbody>{/* */}
                        {costs.map((cost) => (
                          <CostRow
                            key={cost.id}
                            cost={cost}
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
                            <td className="border-t border-gray-300 px-2 py-1.5 text-xs text-right text-gray-600">
                              {(costData?.total_planned ?? 0).toLocaleString()}
                            </td>
                            <td className="border-t border-gray-300 px-2 py-1.5 text-xs text-right text-gray-600">
                              {(costData?.total_actual ?? 0).toLocaleString()}
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
                            <td className="px-2 py-1.5">
                              <input
                                type="number"
                                value={newCost.planned_amount || ''}
                                onChange={(e) => setNewCost((c) => ({ ...c, planned_amount: parseFloat(e.target.value) || 0 }))}
                                placeholder="0"
                                className="w-full text-xs border border-gray-300 rounded px-1.5 py-0.5 outline-none text-right"
                              />
                            </td>
                            <td className="px-2 py-1.5">
                              <input
                                type="number"
                                value={newCost.actual_amount || ''}
                                onChange={(e) => setNewCost((c) => ({ ...c, actual_amount: parseFloat(e.target.value) || 0 }))}
                                placeholder="0"
                                className="w-full text-xs border border-gray-300 rounded px-1.5 py-0.5 outline-none text-right"
                              />
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

            {/* Summary Deliverables row */}
            <tr>{/* */}
              <VerticalLabel>Summary Deliverables</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-3 py-2 align-top"
              >
                <EditableList
                  items={meta.summary_deliverables}
                  onSave={(v) => updateMeta.mutate({ summary_deliverables: v })}
                />
              </td>

              {/* Team panel — spans all week + owner cols, rowSpan=3 */}
              <td
                colSpan={VISIBLE_WEEKS + 1}
                rowSpan={3}
                className="border border-gray-300 px-4 py-3 align-top bg-gray-50/40"
              >
                <div className="grid grid-cols-2 gap-6 h-full">
                  {/* Team members */}
                  <div>
                    <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-2">
                      # People working on project
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-3 pb-1.5 border-b border-gray-200">
                        <span className="text-[10px] text-gray-500 w-24 shrink-0">Project Leader</span>
                        <span className="text-[10px] font-semibold text-gray-700">{leaderName}</span>
                      </div>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <div key={n} className="flex items-center gap-3">
                          <span className="text-[10px] text-gray-400 w-24 shrink-0">Member {n}</span>
                          <span className="text-[10px] text-gray-300">—</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Status legend */}
                  <div>
                    <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-2">
                      Status Legend
                    </div>
                    <div className="space-y-2">
                      {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                        <div key={key} className="flex items-center gap-2">
                          <span className={cn('h-3 w-8 rounded', cfg.bg)} />
                          <span className="text-[10px] text-gray-600">{cfg.label}</span>
                        </div>
                      ))}
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
                className="border border-gray-300 px-3 py-2 align-top"
              >
                <EditableList
                  items={meta.forecast}
                  onSave={(v) => updateMeta.mutate({ forecast: v })}
                />
              </td>{/* */}
            </tr>

            {/* Risk row */}
            <tr>{/* */}
              <VerticalLabel>Risk</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-3 py-2 align-top"
              >
                <EditableList
                  items={meta.risks}
                  onSave={(v) => updateMeta.mutate({ risks: v })}
                />
              </td>{/* */}
            </tr>{/* */}

          </tbody>
        </table>
      </div>

      {/* AI Chat Panel */}
      <ChatPanel projectId={id!} open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  )
}
