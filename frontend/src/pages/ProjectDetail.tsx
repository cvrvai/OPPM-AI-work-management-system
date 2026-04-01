import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { Project, Task } from '@/types'
import { cn, getStatusColor, formatDate, getProgressColor } from '@/lib/utils'
import {
  ArrowLeft,
  Target,
  CheckCircle2,
  Clock,
  LayoutGrid,
  Loader2,
} from 'lucide-react'

const statusIcons = {
  todo: Clock,
  in_progress: Target,
  completed: CheckCircle2,
}

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn: () => ws ? api.get<Project>(`${wsPath}/projects/${id}`) : api.get<Project>(`/projects/${id}`),
  })

  const { data: tasks, isLoading: loadingTasks } = useQuery({
    queryKey: ['tasks', id, ws?.id],
    queryFn: () => ws ? api.get<Task[]>(`${wsPath}/tasks?project_id=${id}`) : api.get<Task[]>(`/projects/${id}/tasks`),
  })

  if (loadingProject) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (!project) return <p className="text-sm text-text-secondary py-12 text-center">Project not found</p>
  const p = project
  const taskList = tasks || []

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
