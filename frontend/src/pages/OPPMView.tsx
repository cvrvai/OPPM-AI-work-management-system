import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Project, Task, OPPMObjective, OPPMTimelineEntry } from '@/types'
import { cn } from '@/lib/utils'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState, useMemo } from 'react'
import {
  startOfWeek,
  endOfWeek,
  addWeeks,
  format,
  isWithinInterval,
  differenceInWeeks,
  parseISO,
} from 'date-fns'

// ── Demo Data ──
const DEMO_PROJECT: Project = {
  id: '1', title: 'OPPM AI System',
  description: 'AI-powered One Page Project Manager',
  status: 'in_progress', priority: 'high', progress: 35,
  start_date: '2026-04-01',
  deadline: '2026-05-24', lead_id: null,
  created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z',
}

const DEMO_OBJECTIVES: OPPMObjective[] = [
  {
    id: 'o1', project_id: '1', title: 'Project Setup & Architecture', owner_id: null, sort_order: 1,
    tasks: [
      { id: 't1', title: 'Scaffold frontend + backend', description: '', project_id: '1', status: 'completed', priority: 'high', progress: 100, project_contribution: 15, due_date: '2026-04-07', created_by: null, completed_at: '2026-04-05T00:00:00Z', created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-05T00:00:00Z' },
      { id: 't1b', title: 'Set up Supabase + auth', description: '', project_id: '1', status: 'completed', priority: 'high', progress: 100, project_contribution: 10, due_date: '2026-04-07', created_by: null, completed_at: '2026-04-06T00:00:00Z', created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-06T00:00:00Z' },
    ],
  },
  {
    id: 'o2', project_id: '1', title: 'OPPM Dashboard & Gantt View', owner_id: null, sort_order: 2,
    tasks: [
      { id: 't2', title: 'OPPM grid component', description: '', project_id: '1', status: 'in_progress', priority: 'high', progress: 60, project_contribution: 15, due_date: '2026-04-14', created_by: null, completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
      { id: 't2b', title: 'Gantt timeline rendering', description: '', project_id: '1', status: 'in_progress', priority: 'high', progress: 30, project_contribution: 10, due_date: '2026-04-14', created_by: null, completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
    ],
  },
  {
    id: 'o3', project_id: '1', title: 'GitHub Integration', owner_id: null, sort_order: 3,
    tasks: [
      { id: 't3', title: 'Webhook handler + HMAC', description: '', project_id: '1', status: 'todo', priority: 'medium', progress: 0, project_contribution: 15, due_date: '2026-04-21', created_by: null, completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
      { id: 't3b', title: 'Repo config UI', description: '', project_id: '1', status: 'todo', priority: 'medium', progress: 0, project_contribution: 5, due_date: '2026-04-21', created_by: null, completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
    ],
  },
  {
    id: 'o4', project_id: '1', title: 'AI Analysis Pipeline', owner_id: null, sort_order: 4,
    tasks: [
      { id: 't4', title: 'Multi-model analysis service', description: '', project_id: '1', status: 'todo', priority: 'high', progress: 0, project_contribution: 20, due_date: '2026-04-28', created_by: null, completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
    ],
  },
  {
    id: 'o5', project_id: '1', title: 'Testing & Demo', owner_id: null, sort_order: 5,
    tasks: [
      { id: 't5', title: 'Demo video + final submission', description: '', project_id: '1', status: 'todo', priority: 'medium', progress: 0, project_contribution: 10, due_date: '2026-05-20', created_by: null, completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
    ],
  },
]

// ── Status dot colors ──
const dotColors: Record<string, string> = {
  completed: 'bg-emerald-500',
  in_progress: 'bg-blue-500',
  at_risk: 'bg-amber-500',
  blocked: 'bg-red-500',
  planned: 'bg-gray-300',
  todo: 'bg-gray-300',
}

const dotBorders: Record<string, string> = {
  completed: 'ring-emerald-200',
  in_progress: 'ring-blue-200',
  at_risk: 'ring-amber-200',
  blocked: 'ring-red-200',
  planned: 'ring-gray-100',
  todo: 'ring-gray-100',
}

export function OPPMView() {
  const { id } = useParams<{ id: string }>()
  const [weekOffset, setWeekOffset] = useState(0)
  const VISIBLE_WEEKS = 8

  const { data: project } = useQuery({
    queryKey: ['project', id],
    queryFn: () => api.get<Project>(`/projects/${id}`),
    placeholderData: DEMO_PROJECT,
  })

  const { data: objectives } = useQuery({
    queryKey: ['oppm-objectives', id],
    queryFn: () => api.get<OPPMObjective[]>(`/projects/${id}/oppm/objectives`),
    placeholderData: DEMO_OBJECTIVES,
  })

  const p = project || DEMO_PROJECT
  const objs = objectives || DEMO_OBJECTIVES

  // Generate week columns starting from project start_date (falls back to created_at)
  const projectStart = startOfWeek(
    parseISO(p.start_date || p.created_at),
    { weekStartsOn: 1 }
  )
  const weeks = useMemo(() => {
    return Array.from({ length: VISIBLE_WEEKS }, (_, i) => {
      const ws = addWeeks(projectStart, weekOffset + i)
      return {
        start: ws,
        end: endOfWeek(ws, { weekStartsOn: 1 }),
        label: format(ws, 'MMM d'),
        weekNum: weekOffset + i + 1,
      }
    })
  }, [weekOffset, projectStart])

  // Get status for a task in a given week
  function getTaskWeekStatus(task: Task, weekStart: Date, weekEnd: Date): string {
    if (!task.due_date) return ''
    const due = parseISO(task.due_date)
    const created = parseISO(task.created_at)

    // Task is within this week's range (between created and due)
    const taskSpansWeek =
      created <= weekEnd && due >= weekStart

    if (!taskSpansWeek) return ''

    if (task.status === 'completed') return 'completed'
    if (task.status === 'in_progress') {
      // Check if at risk (past due or low progress near deadline)
      if (due < new Date()) return 'at_risk'
      return 'in_progress'
    }
    if (task.status === 'todo') {
      if (due < new Date()) return 'blocked'
      return 'planned'
    }
    return 'planned'
  }

  // Calculate objective-level progress
  function getObjectiveProgress(obj: OPPMObjective): number {
    if (!obj.tasks.length) return 0
    const total = obj.tasks.reduce((sum, t) => sum + t.progress, 0)
    return Math.round(total / obj.tasks.length)
  }

  const today = new Date()
  const currentWeekIdx = weeks.findIndex(
    (w) => today >= w.start && today <= w.end
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to={`/projects/${id}`}
          className="rounded-lg border border-border p-2 text-text-secondary hover:bg-surface-alt"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-text">OPPM — {p.title}</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            One Page Project Manager • Gantt + Matrix View
          </p>
        </div>
        <div className="flex items-center gap-1 text-sm">
          <button
            onClick={() => setWeekOffset((o) => o - 1)}
            className="rounded-lg p-1.5 text-text-secondary hover:bg-surface-alt"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-text-secondary px-2">
            W{weekOffset + 1}–W{weekOffset + VISIBLE_WEEKS}
          </span>
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="rounded-lg p-1.5 text-text-secondary hover:bg-surface-alt"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-text-secondary">
        <span className="font-medium text-text">Legend:</span>
        {[
          { label: 'Completed', color: 'bg-emerald-500' },
          { label: 'In Progress', color: 'bg-blue-500' },
          { label: 'At Risk', color: 'bg-amber-500' },
          { label: 'Blocked', color: 'bg-red-500' },
          { label: 'Planned', color: 'bg-gray-300' },
        ].map(({ label, color }) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className={cn('h-2.5 w-2.5 rounded-full', color)} />
            {label}
          </span>
        ))}
      </div>

      {/* OPPM Grid */}
      <div className="overflow-x-auto rounded-xl border border-border bg-white shadow-sm">
        <table className="w-full border-collapse min-w-[900px]">
          <thead>
            <tr className="bg-surface-alt">
              <th className="sticky left-0 z-10 bg-surface-alt border-b border-r border-border px-4 py-3 text-left text-xs font-semibold text-text-secondary w-56">
                Objective / Task
              </th>
              <th className="border-b border-r border-border px-2 py-3 text-center text-xs font-semibold text-text-secondary w-14">
                %
              </th>
              {weeks.map((week, i) => (
                <th
                  key={i}
                  className={cn(
                    'border-b border-r border-border px-2 py-2 text-center text-[10px] font-medium text-text-secondary min-w-[80px]',
                    i === currentWeekIdx && 'bg-primary/5'
                  )}
                >
                  <div className="font-semibold text-text">W{week.weekNum}</div>
                  <div>{week.label}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {objs.map((obj, objIdx) => (
              <>
                {/* Objective Row */}
                <tr key={obj.id} className="bg-slate-50/50">
                  <td className="sticky left-0 z-10 bg-slate-50/50 border-b border-r border-border px-4 py-2.5">
                    <span className="text-sm font-semibold text-text">
                      {objIdx + 1}. {obj.title}
                    </span>
                  </td>
                  <td className="border-b border-r border-border px-2 py-2 text-center">
                    <span className={cn('text-sm font-bold', getProgressColorClass(getObjectiveProgress(obj)))}>
                      {getObjectiveProgress(obj)}%
                    </span>
                  </td>
                  {weeks.map((week, wi) => {
                    // Aggregate status for the objective in this week
                    const statuses = obj.tasks
                      .map((t) => getTaskWeekStatus(t, week.start, week.end))
                      .filter(Boolean)
                    const worstStatus = getWorstStatus(statuses)
                    return (
                      <td
                        key={wi}
                        className={cn(
                          'border-b border-r border-border px-2 py-2 text-center',
                          wi === currentWeekIdx && 'bg-primary/5'
                        )}
                      >
                        {worstStatus && (
                          <div className="flex justify-center">
                            <span
                              className={cn(
                                'h-4 w-4 rounded-full ring-2',
                                dotColors[worstStatus],
                                dotBorders[worstStatus]
                              )}
                            />
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
                {/* Task Rows */}
                {obj.tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-surface-alt/50 transition-colors">
                    <td className="sticky left-0 z-10 bg-white border-b border-r border-border px-4 py-2 pl-8">
                      <span className="text-xs text-text-secondary">{task.title}</span>
                    </td>
                    <td className="border-b border-r border-border px-2 py-2 text-center">
                      <span className={cn('text-xs font-medium', getProgressColorClass(task.progress))}>
                        {task.progress}%
                      </span>
                    </td>
                    {weeks.map((week, wi) => {
                      const status = getTaskWeekStatus(task, week.start, week.end)
                      return (
                        <td
                          key={wi}
                          className={cn(
                            'border-b border-r border-border px-2 py-2 text-center',
                            wi === currentWeekIdx && 'bg-primary/5'
                          )}
                        >
                          {status && (
                            <div className="flex justify-center">
                              <span
                                className={cn(
                                  'h-3 w-3 rounded-full ring-1',
                                  dotColors[status],
                                  dotBorders[status]
                                )}
                              />
                            </div>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary Footer */}
      <div className="grid grid-cols-5 gap-3">
        {objs.map((obj, i) => {
          const progress = getObjectiveProgress(obj)
          return (
            <div key={obj.id} className="rounded-lg border border-border bg-white p-3 shadow-sm">
              <div className="text-[10px] text-text-secondary font-medium mb-1">
                Objective {i + 1}
              </div>
              <div className="text-xs font-semibold text-text mb-2 line-clamp-1">
                {obj.title}
              </div>
              <div className="h-1.5 rounded-full bg-gray-100">
                <div
                  className={cn('h-full rounded-full transition-all', getProgressBg(progress))}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className={cn('text-right text-[10px] font-semibold mt-1', getProgressColorClass(progress))}>
                {progress}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function getProgressColorClass(p: number): string {
  if (p >= 80) return 'text-emerald-600'
  if (p >= 50) return 'text-blue-600'
  if (p >= 25) return 'text-amber-600'
  return 'text-gray-500'
}

function getProgressBg(p: number): string {
  if (p >= 80) return 'bg-emerald-500'
  if (p >= 50) return 'bg-blue-500'
  if (p >= 25) return 'bg-amber-500'
  return 'bg-gray-300'
}

function getWorstStatus(statuses: string[]): string {
  if (statuses.includes('blocked')) return 'blocked'
  if (statuses.includes('at_risk')) return 'at_risk'
  if (statuses.includes('in_progress')) return 'in_progress'
  if (statuses.includes('planned')) return 'planned'
  if (statuses.includes('completed')) return 'completed'
  return ''
}
