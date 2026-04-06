import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import { useChatContext } from '@/hooks/useChatContext'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import type { Project, Task, TaskReport, Priority, TaskStatus, OPPMObjective, OPPMSubObjective, WorkspaceMember } from '@/types'
import { cn, getStatusColor, formatDate } from '@/lib/utils'
import { Skeleton } from '@/components/Skeleton'
import { GanttChart } from '@/components/GanttChart'
import {
  ArrowLeft,
  Target,
  CheckCircle2,
  AlertTriangle,
  Clock,
  LayoutGrid,
  List,
  Loader2,
  Plus,
  X,
  Trash2,
  ChevronRight,
  User,
  CalendarDays,
  Pencil,
  ClipboardList,
  CheckCircle,
  XCircle,
  DollarSign,
  Hash,
  GitBranch,
} from 'lucide-react'

const PRIORITY_COLORS: Record<Priority, string> = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

const PRIORITY_BORDER: Record<Priority, string> = {
  low: 'border-l-slate-300',
  medium: 'border-l-blue-400',
  high: 'border-l-amber-400',
  critical: 'border-l-red-500',
}

const STATUS_ACCENT: Record<TaskStatus, string> = {
  todo: 'border-t-slate-400',
  in_progress: 'border-t-blue-500',
  completed: 'border-t-emerald-500',
}

const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  completed: 'Completed',
}

const STATUS_BADGE: Record<TaskStatus, string> = {
  todo: 'bg-slate-100 text-slate-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-emerald-100 text-emerald-700',
}

const STATUS_ICONS = {
  todo: Clock,
  in_progress: Target,
  completed: CheckCircle2,
}

const NEXT_STATUS: Record<TaskStatus, TaskStatus> = {
  todo: 'in_progress',
  in_progress: 'completed',
  completed: 'todo',
}

// -- Main component --

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const currentUserId = useAuthStore((s) => s.user?.id)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const queryClient = useQueryClient()

  // Redirect to /projects when workspace changes — prevents cross-workspace 404s
  useWorkspaceNavGuard()

  const [showCreate, setShowCreate] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [viewMode, setViewMode] = useState<'board' | 'list' | 'timeline'>('board')

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id, ws?.id],
    queryFn: () => ws ? api.get<Project>(`${wsPath}/projects/${id}`) : api.get<Project>(`/projects/${id}`),
  })

  useChatContext('project', id, project?.title)

  const { data: tasks, isLoading: loadingTasks } = useQuery({
    queryKey: ['tasks', id, ws?.id],
    queryFn: () => ws ? api.get<Task[]>(`${wsPath}/tasks?project_id=${id}`) : api.get<Task[]>(`/projects/${id}/tasks`),
  })

  const { data: objectives } = useQuery({
    queryKey: ['oppm-objectives', id, ws?.id],
    queryFn: () => api.get<OPPMObjective[]>(`${wsPath}/projects/${id}/oppm/objectives`),
    enabled: !!ws,
  })

  const { data: subObjectives } = useQuery({
    queryKey: ['oppm-sub-objectives', id, ws?.id],
    queryFn: () => api.get<OPPMSubObjective[]>(`${wsPath}/projects/${id}/oppm/sub-objectives`),
    enabled: !!ws,
  })

  const { data: members } = useQuery({
    queryKey: ['workspace-members', ws?.id],
    queryFn: () => api.get<WorkspaceMember[]>(`${wsPath}/members`),
    enabled: !!ws,
  })

  const createTask = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const subObjIds = data.sub_objective_ids as string[] | undefined
      const { sub_objective_ids: _removed, ...rest } = data
      void _removed
      const payload = { ...rest, project_id: id }
      const task = await api.post<{ id: string }>(`${wsPath}/tasks`, payload)
      if (subObjIds && subObjIds.length > 0 && task?.id) {
        await api.put(`${wsPath}/projects/${id}/oppm/tasks/${task.id}/sub-objectives`, { sub_objective_ids: subObjIds })
      }
      return task
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', id] })
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', id] })
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
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <div className="rounded-lg border border-border p-2"><ArrowLeft className="h-4 w-4 text-gray-300" /></div>
          <div className="flex-1 space-y-2">
            <Skeleton className="h-7 w-64" />
            <Skeleton className="h-4 w-96" />
          </div>
          <Skeleton className="h-9 w-28 rounded-lg" />
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
        <Skeleton className="h-24 w-full rounded-xl" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-20 w-full rounded-xl" />
              <Skeleton className="h-20 w-full rounded-xl" />
            </div>
          ))}
        </div>
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

  const objectiveMap = new Map((objectives ?? []).map((o) => [o.id, o.title]))
  const memberMap = new Map((members ?? []).map((m) => [m.user_id, m.display_name || m.email || m.user_id.slice(0, 8)]))
  const currentMember = (members ?? []).find((m) => m.user_id === currentUserId)
  const isLead = !p.lead_id || (!!currentMember && currentMember.id === p.lead_id)

  const handleStatusChange = (task: Task) =>
    updateTask.mutate({ taskId: task.id, data: { status: NEXT_STATUS[task.status] } })

  const handleDelete = (task: Task) => {
    if (confirm(`Delete task "${task.title}"?`)) deleteTask.mutate(task.id)
  }

  return (
    <div className="space-y-5">
      {/* -- Header -- */}
      <div className="flex items-start gap-4">
        <Link
          to="/projects"
          className="mt-1 rounded-lg border border-border p-2 text-text-secondary hover:bg-surface-alt transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            {p.project_code && (
              <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-mono font-medium text-slate-600">
                <Hash className="h-3 w-3" />{p.project_code}
              </span>
            )}
            <h1 className="text-2xl font-bold text-text truncate">{p.title}</h1>
            <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', getStatusColor(p.status))}>
              {p.status.replace('_', ' ')}
            </span>
          </div>
          {p.objective_summary && (
            <p className="text-sm font-medium text-primary mt-1">{p.objective_summary}</p>
          )}
          {p.description && (
            <p className="text-sm text-text-secondary mt-0.5 line-clamp-2">{p.description}</p>
          )}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {p.start_date && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-2.5 py-1 text-xs text-text-secondary">
                <CalendarDays className="h-3.5 w-3.5 text-slate-400" />
                Start: {formatDate(p.start_date)}
              </span>
            )}
            {p.deadline && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-2.5 py-1 text-xs text-text-secondary">
                <CalendarDays className="h-3.5 w-3.5 text-primary" />
                Deadline: {formatDate(p.deadline)}
              </span>
            )}
            {p.end_date && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-2.5 py-1 text-xs text-text-secondary">
                <CalendarDays className="h-3.5 w-3.5 text-emerald-500" />
                End: {formatDate(p.end_date)}
              </span>
            )}
            <span className={cn('inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium', PRIORITY_COLORS[p.priority])}>
              {p.priority}
            </span>
            {p.lead && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-2.5 py-1 text-xs text-text-secondary">
                <User className="h-3.5 w-3.5 text-slate-400" />
                {p.lead.display_name || p.lead.email || 'Lead'}
              </span>
            )}
            {(p.budget != null && p.budget > 0) && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-2.5 py-1 text-xs text-text-secondary">
                <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
                {Number(p.budget).toLocaleString()}
              </span>
            )}
            {(p.planning_hours != null && p.planning_hours > 0) && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-2.5 py-1 text-xs text-text-secondary">
                <Clock className="h-3.5 w-3.5 text-blue-500" />
                {Number(p.planning_hours).toLocaleString()}h
              </span>
            )}
          </div>
        </div>
        <Link
          to={`/projects/${id}/oppm`}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors whitespace-nowrap"
        >
          <LayoutGrid className="h-4 w-4" /> OPPM View
        </Link>
      </div>

      {/* -- KPI cards -- */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'Total Tasks', value: taskList.length, icon: Target, iconColor: 'text-primary', bg: 'bg-blue-50' },
          { label: 'Completed', value: tasksByStatus.completed.length, icon: CheckCircle2, iconColor: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'In Progress', value: tasksByStatus.in_progress.length, icon: Clock, iconColor: 'text-blue-500', bg: 'bg-blue-50' },
          { label: 'To Do', value: tasksByStatus.todo.length, icon: List, iconColor: 'text-slate-500', bg: 'bg-slate-50' },
        ].map(({ label, value, icon: Icon, iconColor, bg }) => (
          <div key={label} className="flex items-center gap-3 rounded-xl border border-border bg-white p-4 shadow-sm">
            <div className={cn('flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg', bg)}>
              <Icon className={cn('h-5 w-5', iconColor)} />
            </div>
            <div>
              <p className="text-2xl font-bold text-text leading-none">{value}</p>
              <p className="text-xs text-text-secondary mt-0.5">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* -- Progress -- */}
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="text-sm font-semibold text-text">Overall Progress</span>
            <p className="text-xs text-text-secondary mt-0.5">
              {tasksByStatus.completed.length} of {taskList.length} tasks completed
            </p>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-full border-4 border-primary text-base font-bold text-primary">
            {p.progress}%
          </div>
        </div>
        <div className="h-2 w-full rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${p.progress}%` }}
          />
        </div>
      </div>

      {/* -- Tasks header -- */}
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-text">Tasks</h2>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border border-border bg-white p-0.5 shadow-sm">
            <button
              onClick={() => setViewMode('board')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                viewMode === 'board' ? 'bg-primary text-white shadow-sm' : 'text-text-secondary hover:text-text'
              )}
            >
              <LayoutGrid className="h-3.5 w-3.5" /> Board
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                viewMode === 'list' ? 'bg-primary text-white shadow-sm' : 'text-text-secondary hover:text-text'
              )}
            >
              <List className="h-3.5 w-3.5" /> List
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                viewMode === 'timeline' ? 'bg-primary text-white shadow-sm' : 'text-text-secondary hover:text-text'
              )}
            >
              <GitBranch className="h-3.5 w-3.5" /> Timeline
            </button>
          </div>
          {isLead && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white hover:bg-primary-dark transition-colors"
            >
              <Plus className="h-3.5 w-3.5" /> Add Task
            </button>
          )}
        </div>
      </div>

      {/* -- Modals -- */}
      {showCreate && (
        <TaskForm
          title="Create Task"
          objectives={objectives ?? []}
          subObjectives={subObjectives ?? []}
          members={members ?? []}
          allTasks={taskList}
          onSubmit={(data) => createTask.mutate(data)}
          onCancel={() => setShowCreate(false)}
          isPending={createTask.isPending}
          wsPath={wsPath}
          isLead={isLead}
          currentUserId={currentUserId ?? ''}
        />
      )}
      {editingTask && (
        <TaskForm
          title="Edit Task"
          initial={editingTask}
          objectives={objectives ?? []}
          subObjectives={subObjectives ?? []}
          members={members ?? []}
          allTasks={taskList.filter((t) => t.id !== editingTask.id)}
          onSubmit={(data) => updateTask.mutate({ taskId: editingTask.id, data })}
          onCancel={() => setEditingTask(null)}
          isPending={updateTask.isPending}
          wsPath={wsPath}
          isLead={isLead}
          currentUserId={currentUserId ?? ''}
        />
      )}

      {/* -- Content -- */}
      {loadingTasks ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        </div>
      ) : viewMode === 'board' ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {(['todo', 'in_progress', 'completed'] as const).map((status) => {
            const Icon = STATUS_ICONS[status]
            return (
              <div
                key={status}
                className={cn(
                  'rounded-xl border-t-[3px] border border-border bg-gray-50/60 p-3',
                  STATUS_ACCENT[status]
                )}
              >
                <div className="flex items-center gap-2 mb-3 px-0.5">
                  <Icon className="h-4 w-4 text-text-secondary" />
                  <span className="text-sm font-semibold text-text">{STATUS_LABEL[status]}</span>
                  <span className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center rounded-full border border-border bg-white px-1.5 text-[10px] font-semibold text-text-secondary shadow-sm">
                    {tasksByStatus[status].length}
                  </span>
                </div>
                <div className="space-y-2">
                  {tasksByStatus[status].map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      objectiveName={task.oppm_objective_id ? objectiveMap.get(task.oppm_objective_id) : undefined}
                      ownerName={task.assignee_id ? memberMap.get(task.assignee_id) : undefined}
                      onEdit={() => setEditingTask(task)}
                      onStatusChange={() => handleStatusChange(task)}
                      onDelete={() => handleDelete(task)}
                    />
                  ))}
                  {tasksByStatus[status].length === 0 && (
                    <div className="rounded-lg border-2 border-dashed border-gray-200 py-7 text-center text-xs text-gray-400">
                      No tasks
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : viewMode === 'list' ? (
        <TableView
          tasks={taskList}
          objectiveMap={objectiveMap}
          memberMap={memberMap}
          onEdit={(task) => setEditingTask(task)}
          onStatusChange={handleStatusChange}
          onDelete={handleDelete}
        />
      ) : (
        <GanttChart
          tasks={taskList}
          onTaskClick={(task) => setEditingTask(task)}
        />
      )}
    </div>
  )
}

// -- TaskCard --

function TaskCard({
  task,
  objectiveName,
  ownerName,
  onEdit,
  onStatusChange,
  onDelete,
}: {
  task: Task
  objectiveName?: string
  ownerName?: string
  onEdit: () => void
  onStatusChange: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={cn(
        'group rounded-lg border-l-[3px] border border-border bg-white p-3.5 shadow-sm hover:shadow-md transition-all',
        PRIORITY_BORDER[task.priority]
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h4
          onClick={onEdit}
          className="text-sm font-semibold text-text cursor-pointer hover:text-primary flex-1 leading-snug"
        >
          {task.title}
        </h4>
        <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onStatusChange}
            title={`Move to ${STATUS_LABEL[NEXT_STATUS[task.status]]}`}
            className="rounded p-0.5 text-gray-400 hover:bg-blue-50 hover:text-blue-600 transition-colors"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onDelete}
            className="rounded p-0.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {task.description && (
        <p className="text-xs text-text-secondary line-clamp-2 mt-1">{task.description}</p>
      )}
      {(objectiveName || ownerName) && (
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          {objectiveName && (
            <span className="inline-flex items-center gap-1 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">
              <Target className="h-2.5 w-2.5" /> {objectiveName}
            </span>
          )}
          {ownerName && (
            <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
              <User className="h-2.5 w-2.5" /> {ownerName}
            </span>
          )}
        </div>
      )}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', PRIORITY_COLORS[task.priority])}>
          {task.priority}
        </span>
        <span className="text-[10px] font-semibold text-text-secondary">{task.progress}%</span>
        {(task.start_date || task.due_date) && (
          <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-text-secondary">
            <CalendarDays className="h-2.5 w-2.5" />
            {task.start_date ? formatDate(task.start_date) : '—'}
            {' → '}
            {task.due_date ? formatDate(task.due_date) : '—'}
          </span>
        )}
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            task.progress >= 80 ? 'bg-emerald-500' : task.progress >= 40 ? 'bg-primary' : 'bg-amber-400'
          )}
          style={{ width: `${Math.max(task.progress, 0)}%` }}
        />
      </div>
    </div>
  )
}

// -- TableView --

function TableView({
  tasks,
  objectiveMap,
  memberMap,
  onEdit,
  onStatusChange,
  onDelete,
}: {
  tasks: Task[]
  objectiveMap: Map<string, string>
  memberMap: Map<string, string>
  onEdit: (task: Task) => void
  onStatusChange: (task: Task) => void
  onDelete: (task: Task) => void
}) {
  if (tasks.length === 0) {
    return (
      <div className="rounded-xl border-2 border-dashed border-gray-200 py-14 text-center text-sm text-gray-400">
        No tasks yet. Click <span className="font-medium text-primary">+ Add Task</span> to get started.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-white shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-gray-50/80">
              <th className="w-10 px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">#</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Title</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Status</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Priority</th>
              <th className="w-32 px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Progress</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Objective</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Owner</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Start Date</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Due Date</th>
              <th className="w-24 px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task, index) => (
              <tr
                key={task.id}
                className={cn(
                  'border-b border-border last:border-0 hover:bg-blue-50/30 transition-colors',
                  index % 2 === 1 ? 'bg-gray-50/40' : 'bg-white'
                )}
              >
                <td className="px-4 py-3 text-xs text-text-secondary">{index + 1}</td>
                <td className="px-4 py-3 max-w-[220px]">
                  <button
                    onClick={() => onEdit(task)}
                    className="text-left font-semibold text-text hover:text-primary transition-colors line-clamp-1 w-full"
                  >
                    {task.title}
                  </button>
                  {task.description && (
                    <p className="text-xs text-text-secondary line-clamp-1 mt-0.5">{task.description}</p>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', STATUS_BADGE[task.status])}>
                    {STATUS_LABEL[task.status]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={cn('rounded px-2 py-0.5 text-xs font-medium', PRIORITY_COLORS[task.priority])}>
                    {task.priority}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full',
                          task.progress >= 80 ? 'bg-emerald-500' : task.progress >= 40 ? 'bg-primary' : 'bg-amber-400'
                        )}
                        style={{ width: `${task.progress}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-text-secondary w-8 text-right shrink-0">{task.progress}%</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  {task.oppm_objective_id && objectiveMap.get(task.oppm_objective_id) ? (
                    <span className="inline-flex items-center gap-1 rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] font-medium text-indigo-600 whitespace-nowrap">
                      <Target className="h-3 w-3 shrink-0" />
                      <span className="truncate max-w-[100px]">{objectiveMap.get(task.oppm_objective_id)}</span>
                    </span>
                  ) : (
                    <span className="text-gray-300 text-xs">�</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {task.assignee_id && memberMap.get(task.assignee_id) ? (
                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-600">
                        {(memberMap.get(task.assignee_id) ?? '?')[0].toUpperCase()}
                      </span>
                      <span className="text-xs text-text-secondary truncate max-w-[80px]">{memberMap.get(task.assignee_id)}</span>
                    </span>
                  ) : (
                    <span className="text-gray-300 text-xs">�</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
                  {task.start_date ? formatDate(task.start_date) : <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
                  {task.due_date ? formatDate(task.due_date) : <span className="text-gray-300">�</span>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onEdit(task)}
                      title="Edit"
                      className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-text transition-colors"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onStatusChange(task)}
                      title={`Move to ${STATUS_LABEL[NEXT_STATUS[task.status]]}`}
                      className="rounded p-1 text-gray-400 hover:bg-blue-50 hover:text-blue-600 transition-colors"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onDelete(task)}
                      title="Delete"
                      className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// -- TaskForm --

function TaskForm({
  title,
  initial,
  objectives,
  subObjectives = [],
  members,
  allTasks = [],
  onSubmit,
  onCancel,
  isPending,
  wsPath,
  isLead = false,
  currentUserId = '',
}: {
  title: string
  initial?: Task
  objectives: OPPMObjective[]
  subObjectives?: OPPMSubObjective[]
  members: WorkspaceMember[]
  allTasks?: Task[]
  onSubmit: (data: Record<string, unknown>) => void
  onCancel: () => void
  isPending: boolean
  wsPath: string
  isLead?: boolean
  currentUserId?: string
}) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'details' | 'reports'>('details')
  const [reportForm, setReportForm] = useState({ report_date: new Date().toISOString().slice(0, 10), hours: '', description: '' })
  const [showReportForm, setShowReportForm] = useState(false)

  const reportsQuery = useQuery<TaskReport[]>({
    queryKey: ['task-reports', initial?.id],
    queryFn: () => api.get<TaskReport[]>(`${wsPath}/tasks/${initial!.id}/reports`),
    enabled: !!initial && tab === 'reports',
  })

  const addReport = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post(`${wsPath}/tasks/${initial!.id}/reports`, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['task-reports', initial?.id] }); setReportForm({ report_date: new Date().toISOString().slice(0, 10), hours: '', description: '' }); setShowReportForm(false) },
  })

  const approveReport = useMutation({
    mutationFn: ({ reportId, is_approved }: { reportId: string; is_approved: boolean }) =>
      api.patch<TaskReport>(`${wsPath}/tasks/${initial!.id}/reports/${reportId}/approve`, { is_approved }),
    onSuccess: (updated) => {
      queryClient.setQueryData<TaskReport[]>(
        ['task-reports', initial?.id],
        (old) => old ? old.map((r) => r.id === updated.id ? updated : r) : old,
      )
    },
  })

  const deleteReport = useMutation({
    mutationFn: (reportId: string) => api.delete(`${wsPath}/tasks/${initial!.id}/reports/${reportId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task-reports', initial?.id] }),
  })
  const [form, setForm] = useState({
    title: initial?.title || '',
    description: initial?.description || '',
    priority: initial?.priority || 'medium',
    status: initial?.status || 'todo',
    progress: initial?.progress ?? 0,
    start_date: initial?.start_date || '',
    due_date: initial?.due_date || '',
    oppm_objective_id: initial?.oppm_objective_id || '',
    assignee_id: initial?.assignee_id || '',
  })
  const [dependsOn, setDependsOn] = useState<string[]>(initial?.depends_on ?? [])
  const [subObjIds, setSubObjIds] = useState<string[]>((initial as unknown as Record<string, unknown>)?.sub_objective_ids as string[] ?? [])

  const toggleDependency = (taskId: string) => {
    setDependsOn((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    )
  }

  const toggleSubObj = (soId: string) => {
    setSubObjIds((prev) =>
      prev.includes(soId) ? prev.filter((id) => id !== soId) : [...prev, soId]
    )
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title.trim()) return
    const data: Record<string, unknown> = { ...form, depends_on: dependsOn, sub_objective_ids: subObjIds }
    if (!data.start_date) delete data.start_date
    if (!data.due_date) delete data.due_date
    if (!data.oppm_objective_id) delete data.oppm_objective_id
    if (!data.assignee_id) delete data.assignee_id
    if (!initial) {
      delete data.status
      if (data.progress === 0) delete data.progress
    }
    if (subObjIds.length === 0) delete data.sub_objective_ids
    onSubmit(data)
  }

  const missingPillars: string[] = []
  if (!form.oppm_objective_id) missingPillars.push('Objective')
  if (!form.assignee_id) missingPillars.push('Owner')
  if (!form.due_date) missingPillars.push('Due date')

  const isOppmAligned = missingPillars.length === 0
  const selectedObjective = objectives.find((objective) => objective.id === form.oppm_objective_id)
  const selectedOwner = members.find((member) => member.user_id === form.assignee_id)

  const fieldLabelClass = 'mb-2 block text-[11px] font-semibold uppercase tracking-[0.08em] text-text-secondary'
  const inputClass = 'w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-4 focus:ring-primary/10'
  const selectClass = 'w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-4 focus:ring-primary/10'
  const textareaClass = 'w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-4 focus:ring-primary/10 resize-none'
  const sectionClass = 'rounded-2xl border border-border bg-surface-alt/70 p-4 sm:p-5'
  const sectionEyebrowClass = 'text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onCancel}>
      <form
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-[min(100%-1rem,54rem)] flex-col overflow-hidden rounded-[1.75rem] border border-border bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">
                {initial ? 'Update execution details' : 'Add execution details'}
              </p>
              <h3 className="text-lg font-semibold text-text">{title}</h3>
              <p className="text-sm text-text-secondary">
                Keep the task brief clear, link it to the right objective, and set ownership without crowding the form.
              </p>
            </div>
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          </div>
          {initial && (
            <div className="flex gap-1.5 overflow-x-auto pb-3">
              <button
                type="button"
                onClick={() => setTab('details')}
                className={cn(
                  'flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold transition-colors',
                  tab === 'details'
                    ? 'bg-primary/10 text-primary ring-1 ring-primary/15'
                    : 'bg-surface-alt text-text-secondary hover:text-text'
                )}
              >
                <Pencil className="h-3.5 w-3.5" /> Details
              </button>
              <button
                type="button"
                onClick={() => setTab('reports')}
                className={cn(
                  'flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold transition-colors',
                  tab === 'reports'
                    ? 'bg-primary/10 text-primary ring-1 ring-primary/15'
                    : 'bg-surface-alt text-text-secondary hover:text-text'
                )}
              >
                <ClipboardList className="h-3.5 w-3.5" /> Daily Reports
                {reportsQuery.data && reportsQuery.data.length > 0 && (
                  <span className="ml-1 rounded-full bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-600 ring-1 ring-slate-200">{reportsQuery.data.length}</span>
                )}
              </button>
            </div>
          )}
        </div>

        {tab === 'reports' && initial ? (
          <div className="max-h-[72vh] space-y-4 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-text-secondary">
                Total hours logged: <span className="font-semibold text-text">{reportsQuery.data ? reportsQuery.data.reduce((s, r) => s + r.hours, 0).toFixed(1) : '—'}</span>
              </p>
              {(!initial?.assignee_id || initial.assignee_id === currentUserId) && (
                <button
                  type="button"
                  onClick={() => setShowReportForm(v => !v)}
                  className="inline-flex items-center justify-center gap-1 rounded-xl bg-primary px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Report
                </button>
              )}
            </div>

            {showReportForm && (
              <div className="rounded-2xl border border-border bg-surface-alt/70 p-4 sm:p-5">
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Report entry</p>
                  <h4 className="text-sm font-semibold text-text">New daily report</h4>
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Date</label>
                    <input type="date" value={reportForm.report_date} onChange={e => setReportForm(f => ({ ...f, report_date: e.target.value }))} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Hours</label>
                    <input type="number" min={0.5} max={24} step={0.5} value={reportForm.hours} onChange={e => setReportForm(f => ({ ...f, hours: e.target.value }))} placeholder="e.g. 3.5" className={inputClass} />
                  </div>
                </div>
                <div className="mt-4">
                  <label className={fieldLabelClass}>Description</label>
                  <textarea value={reportForm.description} onChange={e => setReportForm(f => ({ ...f, description: e.target.value }))} rows={3} placeholder="What did you work on?" className={textareaClass} />
                </div>
                <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <button type="button" onClick={() => setShowReportForm(false)} className="rounded-xl border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-white">Cancel</button>
                  <button
                    type="button"
                    disabled={addReport.isPending || !reportForm.hours || !reportForm.report_date}
                    onClick={() => addReport.mutate({ report_date: reportForm.report_date, hours: parseFloat(reportForm.hours), description: reportForm.description })}
                    className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50"
                  >
                    {addReport.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {reportsQuery.isLoading && <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-text-secondary" /></div>}
            {reportsQuery.data && reportsQuery.data.length === 0 && (
              <div className="rounded-2xl border border-dashed border-gray-200 py-10 text-center">
                <ClipboardList className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                <p className="text-sm text-text-secondary">No reports yet</p>
                <p className="text-xs text-gray-400 mt-0.5">Submit a daily report to track your work</p>
              </div>
            )}
            {reportsQuery.data && reportsQuery.data.map(report => (
              <div key={report.id} className={cn('rounded-2xl border px-4 py-3.5 space-y-1.5 shadow-sm', report.is_approved ? 'border-emerald-200 bg-emerald-50' : 'border-border bg-white')}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-text">{report.report_date}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">{report.hours}h</span>
                    {report.is_approved
                      ? <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600"><CheckCircle className="h-3 w-3" /> Approved</span>
                      : <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-600"><Clock className="h-3 w-3" /> Pending</span>
                    }
                  </div>
                  <div className="flex items-center gap-1">
                    {isLead && !report.is_approved && (
                      <button type="button" onClick={() => approveReport.mutate({ reportId: report.id, is_approved: true })} title="Approve" className="rounded p-1 text-emerald-500 hover:bg-emerald-50 transition-colors"><CheckCircle className="h-3.5 w-3.5" /></button>
                    )}
                    {isLead && report.is_approved && (
                      <button type="button" onClick={() => approveReport.mutate({ reportId: report.id, is_approved: false })} title="Revoke approval" className="rounded p-1 text-amber-500 hover:bg-amber-50 transition-colors"><XCircle className="h-3.5 w-3.5" /></button>
                    )}
                    {(isLead || currentUserId === report.reporter_id) && (
                      <button type="button" onClick={() => { if (confirm('Delete this report?')) deleteReport.mutate(report.id) }} title="Delete" className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                    )}
                  </div>
                </div>
                {report.description && <p className="text-xs text-text-secondary">{report.description}</p>}
              </div>
            ))}
          </div>
        ) : (
        <>
        <div className="max-h-[72vh] overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
            <div className="space-y-5 lg:col-span-3">
              <section className={sectionClass}>
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Task brief</p>
                  <h4 className="text-sm font-semibold text-text">What needs to get done?</h4>
                </div>

                <div>
                  <label className={fieldLabelClass}>Title *</label>
                  <input
                    value={form.title}
                    onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                    required
                    placeholder="Task title"
                    className={inputClass}
                    autoFocus
                  />
                </div>

                <div className="mt-4">
                  <label className={fieldLabelClass}>Description</label>
                  <textarea
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    rows={4}
                    placeholder="Add the outcome, key constraints, or handoff notes"
                    className={textareaClass}
                  />
                </div>
              </section>

              <section className={sectionClass}>
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Delivery setup</p>
                  <h4 className="text-sm font-semibold text-text">Schedule, progress, and workflow state</h4>
                </div>

                <div className={cn('grid grid-cols-1 gap-4 md:grid-cols-2', initial && 'xl:grid-cols-3')}>
                  <div>
                    <label className={fieldLabelClass}>Priority</label>
                    <select
                      value={form.priority}
                      onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as Priority }))}
                      className={selectClass}
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>

                  {initial && (
                    <div>
                      <label className={fieldLabelClass}>Status</label>
                      <select
                        value={form.status}
                        onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as TaskStatus }))}
                        className={selectClass}
                      >
                        <option value="todo">To Do</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                      </select>
                    </div>
                  )}

                  <div>
                    <label className={fieldLabelClass}>Progress (%)</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={form.progress}
                      onChange={(e) => setForm((f) => ({ ...f, progress: parseInt(e.target.value) || 0 }))}
                      className={inputClass}
                    />
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Start Date</label>
                    <input
                      type="date"
                      value={form.start_date}
                      onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Due Date</label>
                    <input
                      type="date"
                      value={form.due_date}
                      onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                      className={inputClass}
                    />
                  </div>
                </div>
              </section>
            </div>

            <div className="space-y-5 lg:col-span-2">
              <section className={sectionClass}>
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Ownership and alignment</p>
                  <h4 className="text-sm font-semibold text-text">Connect the task to the delivery plan</h4>
                </div>

                <div>
                  <label className={fieldLabelClass}>Linked Objective</label>
                  {objectives.length > 0 ? (
                    <>
                      <select
                        value={form.oppm_objective_id}
                        onChange={(e) => setForm((f) => ({ ...f, oppm_objective_id: e.target.value }))}
                        className={selectClass}
                      >
                        <option value="">None (not linked to OPPM)</option>
                        {objectives.map((obj, i) => (
                          <option key={obj.id} value={obj.id}>
                            {String.fromCharCode(65 + i)}. {obj.title}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs text-text-secondary">
                        {selectedObjective ? `Currently linked to ${selectedObjective.title}.` : 'Linking an objective keeps the task visible in the OPPM layer.'}
                      </p>
                    </>
                  ) : (
                    <p className="rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm italic text-text-secondary">
                      No objectives yet. Create objectives in OPPM View first.
                    </p>
                  )}
                </div>

                <div className="mt-4">
                  <label className={fieldLabelClass}>Owner</label>
                  {members.length > 0 ? (
                    <>
                      <select
                        value={form.assignee_id}
                        onChange={(e) => setForm((f) => ({ ...f, assignee_id: e.target.value }))}
                        className={selectClass}
                      >
                        <option value="">Unassigned</option>
                        {members.map((m) => (
                          <option key={m.id} value={m.user_id}>
                            {m.display_name || m.email || m.user_id.slice(0, 8)}
                            {m.role === 'owner' ? ' (Owner)' : m.role === 'admin' ? ' (Admin)' : ''}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs text-text-secondary">
                        {selectedOwner ? `Primary owner: ${selectedOwner.display_name || selectedOwner.email || 'Assigned member'}.` : 'Assign an owner to keep accountability clear.'}
                      </p>
                    </>
                  ) : (
                    <p className="rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm italic text-text-secondary">
                      No workspace members found.
                    </p>
                  )}
                </div>
              </section>

              {allTasks.length > 0 && (
                <section className={sectionClass}>
                  <div className="mb-3 space-y-1">
                    <p className={sectionEyebrowClass}>Dependencies</p>
                    <h4 className="text-sm font-semibold text-text">This task depends on</h4>
                    <p className="text-xs text-text-secondary">Select tasks that must be completed before this one can start.</p>
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-1.5">
                    {allTasks.map((t) => (
                      <label
                        key={t.id}
                        className={cn(
                          'flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors',
                          dependsOn.includes(t.id)
                            ? 'border-primary/40 bg-primary/5 text-primary'
                            : 'border-border bg-white text-text hover:bg-surface-alt'
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={dependsOn.includes(t.id)}
                          onChange={() => toggleDependency(t.id)}
                          className="h-3.5 w-3.5 accent-primary"
                        />
                        <span className="flex-1 truncate font-medium">{t.title}</span>
                        <span className={cn(
                          'shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium',
                          STATUS_BADGE[t.status]
                        )}>
                          {STATUS_LABEL[t.status]}
                        </span>
                      </label>
                    ))}
                  </div>
                  {dependsOn.length > 0 && (
                    <p className="mt-2 text-xs text-primary font-medium">
                      {dependsOn.length} dependenc{dependsOn.length === 1 ? 'y' : 'ies'} set
                    </p>
                  )}
                </section>
              )}

              {/* Sub-objectives (OPPM) */}
              {subObjectives.length > 0 && (
                <section className={sectionClass}>
                  <div className="mb-3 space-y-1">
                    <p className={sectionEyebrowClass}>Sub Objectives</p>
                    <h4 className="text-sm font-semibold text-text">Which sub-objectives does this task contribute to?</h4>
                    <p className="text-xs text-text-secondary">Select the OPPM sub-objectives this task helps achieve.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                    {Array.from({ length: 6 }, (_, i) => {
                      const so = subObjectives.find(s => s.position === i + 1)
                      if (!so) return null
                      const checked = subObjIds.includes(so.id)
                      return (
                        <label
                          key={so.id}
                          className={cn(
                            'flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors',
                            checked
                              ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                              : 'border-border bg-white text-text hover:bg-surface-alt'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleSubObj(so.id)}
                            className="h-3.5 w-3.5 accent-indigo-600 shrink-0"
                          />
                          <span className="font-bold text-[10px] shrink-0">{i + 1}.</span>
                          <span className="truncate font-medium">{so.label}</span>
                        </label>
                      )
                    }).filter(Boolean)}
                  </div>
                  {subObjIds.length > 0 && (
                    <p className="mt-2 text-xs text-indigo-600 font-medium">
                      {subObjIds.length} sub-objective{subObjIds.length > 1 ? 's' : ''} linked
                    </p>
                  )}
                </section>
              )}

              <section className={cn(sectionClass, isOppmAligned ? 'border-emerald-200 bg-emerald-50/80' : 'border-amber-200 bg-amber-50/80')}>
                <div className="flex items-start gap-3">
                  <div className={cn('mt-0.5 rounded-full p-2', isOppmAligned ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>
                    {isOppmAligned ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-text">
                      {isOppmAligned ? 'OPPM aligned' : `${missingPillars.length} OPPM field${missingPillars.length > 1 ? 's' : ''} missing`}
                    </p>
                    <p className="text-sm text-text-secondary">
                      {isOppmAligned
                        ? 'Objective, owner, and due date are all set. This task will sit cleanly in the delivery plan.'
                        : `Still missing: ${missingPillars.join(', ')}.`}
                    </p>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-border bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className={cn('text-sm font-semibold', isOppmAligned ? 'text-emerald-700' : 'text-amber-700')}>
              {isOppmAligned ? 'Ready to save' : 'Needs a little more alignment'}
            </p>
            <p className="text-xs text-text-secondary">
              {isOppmAligned ? 'This task has the core OPPM fields in place.' : `Add ${missingPillars.join(', ')} when you want full OPPM coverage.`}
            </p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-alt"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !form.title.trim()}
              className="inline-flex items-center justify-center rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50"
            >
              {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : initial ? 'Save Changes' : 'Create Task'}
            </button>
          </div>
        </div>
        </>
        )}
      </form>
    </div>
  )
}
