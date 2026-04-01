import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Project, Task, CommitAnalysis } from '@/types'
import { cn, getStatusColor, formatDate, formatRelativeTime, getProgressColor } from '@/lib/utils'
import {
  ArrowLeft,
  Target,
  CheckCircle2,
  Clock,
  GitCommitHorizontal,
  Shield,
  TrendingUp,
  LayoutGrid,
} from 'lucide-react'

const DEMO_TASKS: Task[] = [
  {
    id: 't1', title: 'Set up project scaffolding', description: 'Vite + React + TS + Tailwind',
    project_id: '1', status: 'completed', priority: 'high', progress: 100,
    project_contribution: 15, due_date: '2026-04-05', created_by: null,
    completed_at: '2026-04-02T10:00:00Z', created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-02T10:00:00Z',
  },
  {
    id: 't2', title: 'Build OPPM Gantt hybrid view', description: 'Timeline + matrix view',
    project_id: '1', status: 'in_progress', priority: 'high', progress: 40,
    project_contribution: 25, due_date: '2026-04-15', created_by: null,
    completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z',
  },
  {
    id: 't3', title: 'Implement GitHub webhook handler', description: 'FastAPI webhook + HMAC validation',
    project_id: '1', status: 'todo', priority: 'medium', progress: 0,
    project_contribution: 20, due_date: '2026-04-20', created_by: null,
    completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z',
  },
  {
    id: 't4', title: 'AI commit analysis pipeline', description: 'Multi-model analysis service',
    project_id: '1', status: 'todo', priority: 'high', progress: 0,
    project_contribution: 25, due_date: '2026-04-25', created_by: null,
    completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z',
  },
  {
    id: 't5', title: 'Dashboard + reporting', description: 'Stats, charts, project overview',
    project_id: '1', status: 'todo', priority: 'low', progress: 0,
    project_contribution: 15, due_date: '2026-05-01', created_by: null,
    completed_at: null, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z',
  },
]

const statusIcons = {
  todo: Clock,
  in_progress: Target,
  completed: CheckCircle2,
}

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()

  const { data: project } = useQuery({
    queryKey: ['project', id],
    queryFn: () => api.get<Project>(`/projects/${id}`),
    placeholderData: {
      id: id!,
      title: 'OPPM AI System',
      description: 'AI-powered One Page Project Manager with GitHub integration and multi-model commit analysis',
      status: 'in_progress' as const,
      priority: 'high' as const,
      progress: 35,
      start_date: '2026-04-01',
      deadline: '2026-05-24',
      lead_id: null,
      created_at: '2026-04-01T00:00:00Z',
      updated_at: '2026-04-01T00:00:00Z',
    },
  })

  const { data: tasks } = useQuery({
    queryKey: ['tasks', id],
    queryFn: () => api.get<Task[]>(`/projects/${id}/tasks`),
    placeholderData: DEMO_TASKS,
  })

  if (!project) return null
  const p = project
  const taskList = tasks || DEMO_TASKS

  const tasksByStatus = {
    todo: taskList.filter((t) => t.status === 'todo'),
    in_progress: taskList.filter((t) => t.status === 'in_progress'),
    completed: taskList.filter((t) => t.status === 'completed'),
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/projects"
          className="rounded-lg border border-border p-2 text-text-secondary hover:bg-surface-alt"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-text">{p.title}</h1>
            <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', getStatusColor(p.status))}>
              {p.status.replace('_', ' ')}
            </span>
          </div>
          <p className="text-sm text-text-secondary mt-0.5">{p.description}</p>
        </div>
        <Link
          to={`/projects/${id}/oppm`}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          <LayoutGrid className="h-4 w-4" /> OPPM View
        </Link>
      </div>

      {/* Progress Overview */}
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-text">Overall Progress</span>
          <span className="text-lg font-bold text-text">{p.progress}%</span>
        </div>
        <div className="h-2.5 w-full rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${p.progress}%` }}
          />
        </div>
        <div className="mt-3 flex gap-6 text-sm text-text-secondary">
          <span>{tasksByStatus.completed.length} completed</span>
          <span>{tasksByStatus.in_progress.length} in progress</span>
          <span>{tasksByStatus.todo.length} to do</span>
        </div>
      </div>

      {/* Task Board */}
      <div>
        <h2 className="text-base font-semibold text-text mb-4">Tasks</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {(['todo', 'in_progress', 'completed'] as const).map((status) => {
            const Icon = statusIcons[status]
            return (
              <div key={status}>
                <div className="flex items-center gap-2 mb-3">
                  <Icon className="h-4 w-4 text-text-secondary" />
                  <span className="text-sm font-semibold text-text capitalize">
                    {status.replace('_', ' ')}
                  </span>
                  <span className="ml-auto text-xs text-text-secondary">
                    {tasksByStatus[status].length}
                  </span>
                </div>
                <div className="space-y-2">
                  {tasksByStatus[status].map((task) => (
                    <div
                      key={task.id}
                      className="rounded-lg border border-border bg-white p-3.5 shadow-sm hover:shadow-md transition-shadow"
                    >
                      <h4 className="text-sm font-medium text-text mb-1">{task.title}</h4>
                      <p className="text-xs text-text-secondary line-clamp-1 mb-2">
                        {task.description}
                      </p>
                      <div className="flex items-center justify-between">
                        <span className={cn('text-xs font-medium', getProgressColor(task.progress))}>
                          {task.progress}%
                        </span>
                        {task.due_date && (
                          <span className="text-[10px] text-text-secondary">
                            {formatDate(task.due_date)}
                          </span>
                        )}
                      </div>
                      {task.progress > 0 && (
                        <div className="mt-2 h-1 w-full rounded-full bg-gray-100">
                          <div
                            className="h-full rounded-full bg-primary"
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
