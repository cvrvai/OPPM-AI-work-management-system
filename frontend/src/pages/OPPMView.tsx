/**
 * OPPMView — One Page Project Manager
 *
 * Layout mirrors the classic OPPM Excel template:
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  Project Leader: [name]  │ ⊙ OPPM │  Project Name: [title]   │ [progress] │
 * ├──────────────────────────┴────────┴──────────────────────────────────────────│
 * │  Project Objective: [desc]   Deliverable Output: [editable]                 │
 * │  Start: [date]   Deadline: [date]   Status: [badge]   ● Legend              │
 * ├──────┬────────────────────────────┬─────┬─W1─┬─W2─┬─...─┬─W8─┬────────────│
 * │ Sub  │ Major Tasks (Deadline)     │  %  │    │    │     │    │ Owner/Prio  │
 * │ Obj  ├────────────────────────────┼─────┼────┼────┼─────┼────┤            │
 * │  1   │ 1. Objective Title         │     │ ●  │ ●  │     │    │            │
 * │      │   1.1 Task A (due date)    │ 60% │ ●  │ ○  │     │    │  high      │
 * │  2   │ 2. Objective Title         │     │    │    │ ●   │    │            │
 * │      │   2.1 Task B (due date)    │ 30% │    │    │ ●   │ ○  │  medium    │
 * ├──────┼────────────────────────────┼─────┴────┴────┴─────┴────┴────────────│
 * │ Summ │ 1. Feature 1               │  Team Members + Status Legend (spans) │
 * │ Del. │ 2. Feature 2               │                                        │
 * ├──────┼────────────────────────────┤                                        │
 * │ Fore │ 1. Expectation 1           │                                        │
 * │ cast │ 2. Expectation 2           │                                        │
 * ├──────┼────────────────────────────┤                                        │
 * │ Risk │ 1. Risk 1                  │                                        │
 * │      │ 2. Risk 2                  │                                        │
 * └──────────────────────────────────────────────────────────────────────────────┘
 */

import React, { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { Project, Task, OPPMObjective } from '@/types'
import { cn, formatDate } from '@/lib/utils'
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2, Target, Check, X } from 'lucide-react'
import { startOfWeek, endOfWeek, addWeeks, format, parseISO } from 'date-fns'
import { useAuthStore } from '@/stores/authStore'

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────
interface OPPMMetadata {
  deliverable_output?: string
  summary_deliverables?: string[]
  forecast?: string[]
  risks?: string[]
}

// ─────────────────────────────────────────────────────────────
// Status helpers
// ─────────────────────────────────────────────────────────────
const DOT_BG: Record<string, string> = {
  completed: 'bg-emerald-500',
  in_progress: 'bg-blue-500',
  at_risk: 'bg-amber-400',
  blocked: 'bg-red-500',
  planned: 'bg-gray-300',
}

function StatusDot({ status }: { status: string }) {
  return (
    <span
      className={cn(
        'inline-block h-3 w-3 rounded-full mx-auto',
        DOT_BG[status] ?? 'bg-gray-200'
      )}
    />
  )
}

function getWorstStatus(statuses: string[]): string {
  if (statuses.includes('blocked')) return 'blocked'
  if (statuses.includes('at_risk')) return 'at_risk'
  if (statuses.includes('in_progress')) return 'in_progress'
  if (statuses.includes('planned')) return 'planned'
  if (statuses.includes('completed')) return 'completed'
  return ''
}

function getTaskWeekStatus(task: Task, weekStart: Date, weekEnd: Date): string {
  if (!task.due_date) return ''
  const due = parseISO(task.due_date)
  const created = parseISO(task.created_at)
  if (created > weekEnd || due < weekStart) return ''
  if (task.status === 'completed') return 'completed'
  if (task.status === 'in_progress') return due < new Date() ? 'at_risk' : 'in_progress'
  if (task.status === 'todo') return due < new Date() ? 'blocked' : 'planned'
  return 'planned'
}

// ─────────────────────────────────────────────────────────────
// Editable inline text field
// ─────────────────────────────────────────────────────────────
function EditableField({
  value,
  onSave,
  placeholder = 'Click to edit…',
}: {
  value: string
  onSave: (v: string) => void
  placeholder?: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  if (editing) {
    return (
      <span className="inline-flex items-center gap-1">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { onSave(draft); setEditing(false) }
            if (e.key === 'Escape') { setDraft(value); setEditing(false) }
          }}
          className="text-xs border border-primary/60 rounded px-1.5 py-0.5 outline-none min-w-[160px]"
        />
        <button onClick={() => { onSave(draft); setEditing(false) }} className="text-emerald-600 hover:text-emerald-700">
          <Check className="h-3 w-3" />
        </button>
        <button onClick={() => { setDraft(value); setEditing(false) }} className="text-gray-400 hover:text-gray-600">
          <X className="h-3 w-3" />
        </button>
      </span>
    )
  }

  return (
    <span
      onClick={() => { setDraft(value); setEditing(true) }}
      className="cursor-pointer hover:bg-amber-50 rounded px-0.5 text-xs text-gray-700 group border border-transparent hover:border-amber-200"
    >
      {value || <em className="not-italic text-gray-400">{placeholder}</em>}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────
// Editable numbered list (for Deliverables / Forecast / Risks)
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
              className="flex-1 text-xs border border-primary/50 rounded px-1.5 py-0.5 outline-none focus:border-primary"
            />
          </div>
        ))}
        <div className="flex gap-2 mt-1.5">
          <button
            onClick={() => { onSave(draft); setEditing(false) }}
            className="text-[10px] bg-primary text-white rounded px-2 py-0.5 font-medium hover:bg-primary-dark"
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
      <div className="text-[10px] text-primary/0 group-hover:text-primary/50 mt-0.5 transition-colors">
        ✎ click to edit
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Priority badge (compact, single letter)
// ─────────────────────────────────────────────────────────────
function PriorityBadge({ priority }: { priority: string }) {
  const cls =
    priority === 'critical' ? 'bg-red-100 text-red-700 ring-red-200' :
    priority === 'high'     ? 'bg-orange-100 text-orange-700 ring-orange-200' :
    priority === 'medium'   ? 'bg-blue-100 text-blue-700 ring-blue-200' :
                              'bg-gray-100 text-gray-500 ring-gray-200'
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center h-5 w-5 rounded-full text-[9px] font-bold ring-1 uppercase',
        cls
      )}
    >
      {priority[0]}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────
// Vertical text cell label (for bottom section rows)
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

// ═════════════════════════════════════════════════════════════
// Main OPPMView Component
// ═════════════════════════════════════════════════════════════
export function OPPMView() {
  const { id } = useParams<{ id: string }>()
  const [weekOffset, setWeekOffset] = useState(0)
  const VISIBLE_WEEKS = 8
  // Total columns: Sub Obj(1) + Major Tasks(1) + %(1) + Weeks(8) + Owner(1) = 12
  const TOTAL_COLS = VISIBLE_WEEKS + 4

  const user = useAuthStore((s) => s.user)
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn: () => ws ? api.get<Project>(`${wsPath}/projects/${id}`) : api.get<Project>(`/projects/${id}`),
  })

  const { data: objectives, isLoading: loadingObjectives } = useQuery({
    queryKey: ['oppm-objectives', id, ws?.id],
    queryFn: () => ws
      ? api.get<OPPMObjective[]>(`${wsPath}/projects/${id}/oppm/objectives`)
      : api.get<OPPMObjective[]>(`/projects/${id}/oppm/objectives`),
  })

  // ── All hooks before early returns ──────────────────────────
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

  const updateMeta = useMutation({
    mutationFn: (patch: OPPMMetadata) =>
      ws
        ? api.put(`${wsPath}/projects/${id}`, { metadata: { ...meta, ...patch } })
        : api.put(`/projects/${id}`, { metadata: { ...meta, ...patch } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', id] }),
  })

  // ── Early returns ────────────────────────────────────────────
  if (loadingProject || loadingObjectives) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (!project) return (
    <p className="text-sm text-text-secondary py-12 text-center">Project not found</p>
  )

  const p = project
  const objs = objectives ?? []
  const leaderName = user?.user_metadata?.full_name ?? user?.email?.split('@')[0] ?? 'Project Leader'
  const today = new Date()
  const currentWeekIdx = weeks.findIndex((w) => today >= w.start && today <= w.end)

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className="space-y-4">

      {/* ── Navigation bar ── */}
      <div className="flex items-center gap-3">
        <Link
          to={`/projects/${id}`}
          className="rounded-lg border border-border p-2 text-text-secondary hover:bg-surface-alt"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-text">OPPM — {p.title}</h1>
          <p className="text-xs text-text-secondary">One Page Project Manager · Gantt + Matrix View</p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setWeekOffset((o) => o - 1)}
            className="rounded-lg border border-border p-1.5 text-text-secondary hover:bg-surface-alt"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-text-secondary px-3 font-medium">
            W{weekOffset + 1} – W{weekOffset + VISIBLE_WEEKS}
          </span>
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="rounded-lg border border-border p-1.5 text-text-secondary hover:bg-surface-alt"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════
          OPPM SHEET
      ══════════════════════════════════════════════════════════ */}
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
          <colgroup>
            <col style={{ width: '40px' }} />{/* Sub Obj */}
            <col style={{ width: '220px' }} />{/* Major Tasks */}
            <col style={{ width: '38px' }} />{/* % */}
            {Array.from({ length: VISIBLE_WEEKS }).map((_, i) => (
              <col key={i} style={{ width: '68px' }} />
            ))}
            <col style={{ width: '72px' }} />{/* Owner / Priority */}
          </colgroup>

          {/* ──────────────────────────────────────────────────────
              HEADER — 3 rows
          ────────────────────────────────────────────────────── */}
          <thead>

            {/* Row 1: Project Leader | Logo | Project Name | Progress */}
            <tr>
              <td
                colSpan={3}
                className="border border-gray-300 px-3 py-2 bg-gray-50"
              >
                <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider">
                  Project Leader
                </div>
                <div className="text-sm font-bold text-gray-800">{leaderName}</div>
              </td>

              <td
                colSpan={1}
                className="border border-gray-300 px-2 py-2 text-center bg-primary/5"
              >
                <div className="flex flex-col items-center justify-center gap-0.5">
                  <Target className="h-4 w-4 text-primary" />
                  <div className="text-[10px] font-bold text-primary leading-none">OPPM</div>
                </div>
              </td>

              {/* Project Name spans W2–W8 (cols 5–11) */}
              <td
                colSpan={VISIBLE_WEEKS - 1}
                className="border border-gray-300 px-3 py-2 bg-gray-50"
              >
                <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider">
                  Project Name
                </div>
                <div className="text-sm font-bold text-gray-800">{p.title}</div>
              </td>

              {/* Progress / Status — Owner column */}
              <td className="border border-gray-300 px-2 py-2 bg-gray-50 text-center">
                <div className="text-[9px] text-gray-400">Progress</div>
                <div className="text-base font-black text-primary">{p.progress}%</div>
              </td>
            </tr>

            {/* Row 2: Objective + Output | Dates + Legend */}
            <tr>
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
                    <EditableField
                      value={meta.deliverable_output}
                      onSave={(v) => updateMeta.mutate({ deliverable_output: v })}
                      placeholder="Click to add deliverable output…"
                    />
                  </div>
                </div>
              </td>

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
                  {[
                    { label: 'Completed', color: 'bg-emerald-500' },
                    { label: 'In Progress', color: 'bg-blue-500' },
                    { label: 'At Risk',     color: 'bg-amber-400' },
                    { label: 'Blocked',     color: 'bg-red-500'   },
                    { label: 'Planned',     color: 'bg-gray-300'  },
                  ].map(({ label, color }) => (
                    <span key={label} className="flex items-center gap-1 text-[10px] text-gray-500">
                      <span className={cn('h-2 w-2 rounded-full shrink-0', color)} />
                      {label}
                    </span>
                  ))}
                </div>
              </td>
            </tr>

            {/* Row 3: Column headers */}
            <tr className="bg-gray-100">
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
                      ? 'bg-primary/15 text-primary'
                      : 'text-gray-500'
                  )}
                >
                  <div className="font-black">W{week.weekNum}</div>
                  <div className="font-normal text-[8px] text-gray-400 mt-0.5">{week.label}</div>
                </th>
              ))}
              <th className="border border-gray-300 px-1 py-2 text-center text-[9px] font-bold text-gray-600 uppercase tracking-wide">
                Owner /<br />Priority
              </th>
            </tr>
          </thead>

          {/* ──────────────────────────────────────────────────────
              BODY — Main OPPM Grid + Bottom Section
          ────────────────────────────────────────────────────── */}
          <tbody>

            {/* ── Empty state ── */}
            {objs.length === 0 && (
              <tr>
                <td
                  colSpan={TOTAL_COLS}
                  className="border border-gray-200 py-14 text-center text-sm text-gray-400 italic"
                >
                  No objectives or tasks yet. Open the project detail page to add OPPM objectives and tasks.
                </td>
              </tr>
            )}

            {/* ── Objectives + Tasks rows ── */}
            {objs.map((obj, objIdx) => {
              const taskCount = obj.tasks.length
              // Sub Obj cell spans: 1 (obj row) + taskCount (task rows); min 1
              const subObjSpan = 1 + Math.max(taskCount, 1)

              return (
                <React.Fragment key={obj.id}>

                  {/* Objective header row */}
                  <tr className="bg-slate-50/80">
                    {/* Sub Obj # — spans across all task rows below */}
                    <td
                      rowSpan={subObjSpan}
                      className="border border-gray-300 text-center font-black text-xl text-primary align-middle"
                      style={{ backgroundColor: 'rgba(26,86,219,0.06)' }}
                    >
                      {objIdx + 1}
                    </td>

                    {/* Objective title spans Major Tasks + % cols */}
                    <td
                      colSpan={2}
                      className="border border-gray-300 px-3 py-1.5 font-semibold text-sm text-gray-800"
                    >
                      <span className="text-primary font-black mr-1.5">{objIdx + 1}.</span>
                      {obj.title}
                    </td>

                    {/* Week aggregate dots for this objective */}
                    {weeks.map((week, wi) => {
                      const statuses = obj.tasks
                        .map((t) => getTaskWeekStatus(t, week.start, week.end))
                        .filter(Boolean)
                      const worst = getWorstStatus(statuses)
                      return (
                        <td
                          key={wi}
                          className={cn(
                            'border border-gray-300 text-center p-1 bg-slate-50/80',
                            wi === currentWeekIdx && 'bg-primary/8'
                          )}
                        >
                          {worst && <StatusDot status={worst} />}
                        </td>
                      )
                    })}

                    {/* Owner — placeholder for objective row */}
                    <td className="border border-gray-300 p-1 text-center text-gray-300 text-xs bg-slate-50/80">
                      —
                    </td>
                  </tr>

                  {/* Task rows (or empty row if no tasks) */}
                  {taskCount === 0 ? (
                    <tr>
                      <td
                        colSpan={TOTAL_COLS - 1}
                        className="border border-gray-300 px-3 py-1.5 text-xs text-gray-400 italic"
                      >
                        No tasks assigned to this objective
                      </td>
                    </tr>
                  ) : (
                    obj.tasks.map((task, taskIdx) => (
                      <tr
                        key={task.id}
                        className="hover:bg-amber-50/20 transition-colors"
                      >
                        {/* Sub Obj col covered by rowSpan above */}

                        {/* Task name + due date */}
                        <td className="border border-gray-300 px-3 py-1.5 text-sm">
                          <span className="text-primary font-semibold text-[11px] mr-1.5">
                            {objIdx + 1}.{taskIdx + 1}
                          </span>
                          <span className="text-gray-700">{task.title}</span>
                          {task.due_date && (
                            <span className="text-[10px] text-gray-400 ml-1.5">
                              ({formatDate(task.due_date)})
                            </span>
                          )}
                        </td>

                        {/* Progress % */}
                        <td className="border border-gray-300 text-center p-1">
                          <span
                            className={cn(
                              'text-[11px] font-bold',
                              task.progress >= 80 ? 'text-emerald-600' :
                              task.progress >= 50 ? 'text-blue-600'    :
                              task.progress >= 25 ? 'text-amber-600'   :
                                                    'text-gray-400'
                            )}
                          >
                            {task.progress > 0 ? `${task.progress}%` : '—'}
                          </span>
                        </td>

                        {/* Week status dots */}
                        {weeks.map((week, wi) => {
                          const s = getTaskWeekStatus(task, week.start, week.end)
                          return (
                            <td
                              key={wi}
                              className={cn(
                                'border border-gray-300 text-center p-1',
                                wi === currentWeekIdx && 'bg-primary/5'
                              )}
                            >
                              {s && <StatusDot status={s} />}
                            </td>
                          )
                        })}

                        {/* Owner / Priority */}
                        <td className="border border-gray-300 p-1 text-center">
                          <PriorityBadge priority={task.priority} />
                        </td>
                      </tr>
                    ))
                  )}
                </React.Fragment>
              )
            })}

            {/* ══════════════════════════════════════════════════════
                BOTTOM SECTION — Summary Deliverables / Forecast / Risk
                Columns: VerticalLabel(1) | Items(colSpan=2) | TeamPanel(colSpan=WEEKS+1, rowSpan=3)
            ══════════════════════════════════════════════════════ */}

            {/* Summary Deliverables row */}
            <tr>
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

              {/* Team panel — spans all week + owner cols, rowSpan=3 covers all 3 bottom rows */}
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
                      {[
                        { label: 'Completed',   color: 'bg-emerald-500' },
                        { label: 'In Progress', color: 'bg-blue-500'    },
                        { label: 'At Risk',     color: 'bg-amber-400'   },
                        { label: 'Blocked',     color: 'bg-red-500'     },
                        { label: 'Planned',     color: 'bg-gray-300'    },
                      ].map(({ label, color }) => (
                        <div key={label} className="flex items-center gap-2">
                          <span className={cn('h-3 w-8 rounded', color)} />
                          <span className="text-[10px] text-gray-600">{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              </td>
            </tr>

            {/* Forecast row */}
            <tr>
              <VerticalLabel>Forecast</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-3 py-2 align-top"
              >
                <EditableList
                  items={meta.forecast}
                  onSave={(v) => updateMeta.mutate({ forecast: v })}
                />
              </td>
              {/* Team panel covered by rowSpan=3 above */}
            </tr>

            {/* Risk row */}
            <tr>
              <VerticalLabel>Risk</VerticalLabel>
              <td
                colSpan={2}
                className="border border-gray-300 px-3 py-2 align-top"
              >
                <EditableList
                  items={meta.risks}
                  onSave={(v) => updateMeta.mutate({ risks: v })}
                />
              </td>
              {/* Team panel covered by rowSpan=3 above */}
            </tr>

          </tbody>
        </table>
      </div>
    </div>
  )
}
