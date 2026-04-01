import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { Project, Task, Priority, TaskStatus } from '@/types'
import { cn, getStatusColor, formatDate, getProgressColor } from '@/lib/utils'
import {
  ArrowLeft,
  Target,
  CheckCircle2,
  Clock,
  LayoutGrid,
  Loader2,
  Plus,
  X,
  Trash2,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'

const statusIcons = {
  todo: Clock,
  in_progress: Target,
  completed: CheckCircle2,
}

const PRIORITY_COLORS: Record<Priority, string> = {
  low: 'bg-gray-100 text-gray-600',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

const NEXT_STATUS: Record<TaskStatus, TaskStatus> = {
  todo: 'in_progress',
  in_progress: 'completed',
  completed: 'todo',
}

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const queryClient = useQueryClient()

  const [showCreate, setShowCreate] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn: () => ws ? api.get<Project>(`${wsPath}/projects/${id}`) : api.get<Project>(`/projects/${id}`),
  })

  const { data: tasks, isLoading: loadingTasks } = useQuery({
    queryKey: ['tasks', id, ws?.id],
    queryFn: () => ws ? api.get<Task[]>(`${wsPath}/tasks?project_id=${id}`) : api.get<Task[]>(`/projects/${id}/tasks`),
  })

  // ── Mutations ──

  const createTask = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post(`${wsPath}/tasks`, { ...data, project_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', id] })
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      setShowCreate(false)
    },
  })

  const updateTask = useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: Record<string, unknown> }) =>
      api.put(`${wsPath}/tasks/${taskId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', id] })
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      setEditingTask(null)
    },
  })

  const deleteTask = useMutation({
    mutationFn: (taskId: string) => api.delete(`${wsPath}/tasks/${taskId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', id] })
      queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
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

      {/* Task Board Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-text">Tasks</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Task
        </button>
      </div>

      {/* Create Task Modal */}
      {showCreate && (
        <TaskForm
          title="Create Task"
          onSubmit={(data) => createTask.mutate(data)}
          onCancel={() => setShowCreate(false)}
          isPending={createTask.isPending}
        />
      )}

      {/* Edit Task Modal */}
      {editingTask && (
        <TaskForm
          title="Edit Task"
          initial={editingTask}
          onSubmit={(data) => updateTask.mutate({ taskId: editingTask.id, data })}
          onCancel={() => setEditingTask(null)}
          isPending={updateTask.isPending}
        />
      )}

      {/* Task Board */}
      {loadingTasks ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        </div>
      ) : (
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
                    <TaskCard
                      key={task.id}
                      task={task}
                      onEdit={() => setEditingTask(task)}
                      onStatusChange={() =>
                        updateTask.mutate({
                          taskId: task.id,
                          data: { status: NEXT_STATUS[task.status] },
                        })
                      }
                      onDelete={() => {
                        if (confirm(`Delete task "${task.title}"?`)) {
                          deleteTask.mutate(task.id)
                        }
                      }}
                    />
                  ))}
                  {tasksByStatus[status].length === 0 && (
                    <div className="rounded-lg border-2 border-dashed border-gray-200 py-6 text-center text-xs text-gray-400">
                      No tasks
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── TaskCard ──

function TaskCard({
  task,
  onEdit,
  onStatusChange,
  onDelete,
}: {
  task: Task
  onEdit: () => void
  onStatusChange: () => void
  onDelete: () => void
}) {
  return (
    <div className="group rounded-lg border border-border bg-white p-3.5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <h4
          onClick={onEdit}
          className="text-sm font-medium text-text cursor-pointer hover:text-primary flex-1"
        >
          {task.title}
        </h4>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onStatusChange}
            title={`Move to ${NEXT_STATUS[task.status].replace('_', ' ')}`}
            className="text-gray-400 hover:text-blue-600"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <button onClick={onDelete} className="text-gray-400 hover:text-red-500">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {task.description && (
        <p className="text-xs text-text-secondary line-clamp-2 mt-1">{task.description}</p>
      )}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', PRIORITY_COLORS[task.priority])}>
          {task.priority}
        </span>
        <span className={cn('text-xs font-medium', getProgressColor(task.progress))}>
          {task.progress}%
        </span>
        {task.due_date && (
          <span className="text-[10px] text-text-secondary ml-auto">
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
  )
}

// ── TaskForm (create / edit modal) ──

function TaskForm({
  title,
  initial,
  onSubmit,
  onCancel,
  isPending,
}: {
  title: string
  initial?: Task
  onSubmit: (data: Record<string, unknown>) => void
  onCancel: () => void
  isPending: boolean
}) {
  const [form, setForm] = useState({
    title: initial?.title || '',
    description: initial?.description || '',
    priority: initial?.priority || 'medium',
    status: initial?.status || 'todo',
    progress: initial?.progress ?? 0,
    due_date: initial?.due_date || '',
    project_contribution: initial?.project_contribution ?? 0,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title.trim()) return
    const data: Record<string, unknown> = { ...form }
    if (!data.due_date) delete data.due_date
    // For create, don't send status/progress defaults that are already defaults
    if (!initial) {
      delete data.status
      if (data.progress === 0) delete data.progress
    }
    onSubmit(data)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-xl border border-border bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h3 className="font-semibold text-text">{title}</h3>
          <button type="button" onClick={onCancel} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Title *</label>
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              autoFocus
            />
          </div>
          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={3}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 resize-none"
            />
          </div>
          {/* Row: priority + status */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Priority</label>
              <select
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as Priority }))}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            {initial && (
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Status</label>
                <select
                  value={form.status}
                  onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as TaskStatus }))}
                  className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
                >
                  <option value="todo">To Do</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
            )}
          </div>
          {/* Row: progress + due date */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Progress (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                value={form.progress}
                onChange={(e) => setForm((f) => ({ ...f, progress: parseInt(e.target.value) || 0 }))}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Due Date</label>
              <input
                type="date"
                value={form.due_date}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>
          {/* Project weight */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Project Contribution Weight (0-100)</label>
            <input
              type="number"
              min={0}
              max={100}
              value={form.project_contribution}
              onChange={(e) => setForm((f) => ({ ...f, project_contribution: parseInt(e.target.value) || 0 }))}
              className="w-full max-w-[120px] rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-alt"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending || !form.title.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : initial ? 'Save Changes' : 'Create Task'}
          </button>
        </div>
      </form>
    </div>
  )
}
