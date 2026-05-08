import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { optimisticUpdateInList, rollbackOnError } from '@/lib/utils/optimisticHelpers'
import { updateEntityInCache } from '@/lib/utils/queryNormalizer'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import { useChatContext } from '@/hooks/useChatContext'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import type { Project, Task, TaskReport, Priority, TaskStatus, OPPMObjective, OPPMSubObjective, WorkspaceMember } from '@/types'
import { cn, getStatusColor, formatDate } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'
import { GanttChart } from '@/components/features/GanttChart'
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
  Download,
  FileText,
} from 'lucide-react'
import { exportTasksCSV, exportTasksPDF } from '@/lib/domain/taskReport'
import { TaskCard } from './project-detail/TaskCard'
import { TableView } from './project-detail/TableView'
import { TaskForm } from './project-detail/TaskForm'
import { PRIORITY_COLORS, PRIORITY_BORDER, STATUS_ACCENT, STATUS_LABEL, STATUS_BADGE, STATUS_ICONS, NEXT_STATUS } from './project-detail/constants'



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
    queryFn: () => api.get<Project>(`${wsPath}/projects/${id}`),
    enabled: !!ws && !!id,
  })

  useChatContext('project', id, project?.title)

  const { data: tasks, isLoading: loadingTasks } = useQuery({
    queryKey: ['tasks', id, ws?.id],
    queryFn: () => api.get<Task[]>(`${wsPath}/tasks?project_id=${id}`),
    enabled: !!ws && !!id,
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
    onMutate: async ({ taskId, data }) => {
      await queryClient.cancelQueries({ queryKey: ['tasks', id] })
      const previous = optimisticUpdateInList<Task>(queryClient, ['tasks', id], {
        id: taskId,
        ...data,
      } as Partial<Task> & { id: string })
      return previous
    },
    onError: (_err, _vars, context) => {
      rollbackOnError(queryClient, ['tasks', id], context)
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['tasks', id] })
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      // Also update the task in any project list caches
      if (variables.data && typeof variables.data === 'object') {
        updateEntityInCache(queryClient, { id: variables.taskId, ...variables.data } as Task, [['projects']])
      }
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

  if (!ws) {
    return <p className="py-12 text-center text-sm text-text-secondary">Select a workspace to view this project.</p>
  }

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
        <div className="flex items-center gap-2">
          {(!p.methodology || p.methodology === 'oppm' || p.methodology === 'hybrid') && (
            <Link
              to={`/projects/${id}/oppm`}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors whitespace-nowrap"
            >
              <LayoutGrid className="h-4 w-4" /> OPPM View
            </Link>
          )}
          {(p.methodology === 'agile' || p.methodology === 'hybrid') && (
            <Link
              to={`/projects/${id}/agile`}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors whitespace-nowrap"
            >
              <LayoutGrid className="h-4 w-4" /> Agile Board
            </Link>
          )}
          {(p.methodology === 'waterfall' || p.methodology === 'hybrid') && (
            <Link
              to={`/projects/${id}/waterfall`}
              className="flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 transition-colors whitespace-nowrap"
            >
              <LayoutGrid className="h-4 w-4" /> Waterfall Phases
            </Link>
          )}
        </div>
      </div>

      {/* -- KPI cards -- */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'Total Tasks', value: taskList.length, icon: Target, iconColor: 'text-primary', bg: 'bg-blue-50' },
          { label: 'Completed', value: tasksByStatus.completed.length, icon: CheckCircle2, iconColor: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'In Progress', value: tasksByStatus.in_progress.length, icon: Clock, iconColor: 'text-blue-500', bg: 'bg-blue-50' },
          { label: 'To Do', value: tasksByStatus.todo.length, icon: List, iconColor: 'text-slate-500', bg: 'bg-slate-50' },
        ].map(({ label, value, icon: Icon, iconColor, bg }) => (
          <div key={label} className="flex items-center gap-3 rounded-lg border border-border bg-white p-4">
            <div className={cn('flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md bg-surface-alt border border-border', bg)}>
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
      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="text-sm font-semibold text-text">Overall Progress</span>
            <p className="text-xs text-text-secondary mt-0.5">
              {tasksByStatus.completed.length} of {taskList.length} tasks completed
            </p>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-full border-4 border-border text-base font-bold text-text">
            {p.progress}%
          </div>
        </div>
        <div className="h-2 w-full rounded-full bg-surface-alt">
          <div
            className="h-full rounded-full bg-text-secondary transition-all duration-500"
            style={{ width: `${p.progress}%` }}
          />
        </div>
      </div>

      {/* -- Tasks header -- */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-text">Tasks</h2>
          {taskList.length === 0 && isLead && (
            <p className="text-xs text-text-secondary mt-0.5">
              Start by creating <strong>main tasks</strong>, then add <strong>sub-tasks</strong> under each one.
            </p>
          )}
          {taskList.length > 0 && (
            <p className="text-xs text-text-secondary mt-0.5">
              {taskList.filter(t => !t.parent_task_id).length} main tasks · {taskList.filter(t => t.parent_task_id).length} sub-tasks
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => exportTasksCSV(taskList, objectiveMap, memberMap, p)}
            disabled={taskList.length === 0}
            className="flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-alt transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Download tasks as CSV"
          >
            <Download className="h-3.5 w-3.5" /> CSV
          </button>
          <button
            onClick={() => exportTasksPDF(taskList, objectiveMap, memberMap, p)}
            disabled={taskList.length === 0}
            className="flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-alt transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Download tasks as PDF report"
          >
            <FileText className="h-3.5 w-3.5" /> PDF
          </button>
          <div className="flex items-center rounded-md border border-border bg-white p-0.5">
            <button
              onClick={() => setViewMode('board')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                viewMode === 'board' ? 'bg-primary text-white' : 'text-text-secondary hover:text-text'
              )}
            >
              <LayoutGrid className="h-3.5 w-3.5" /> Board
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                viewMode === 'list' ? 'bg-primary text-white' : 'text-text-secondary hover:text-text'
              )}
            >
              <List className="h-3.5 w-3.5" /> List
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                viewMode === 'timeline' ? 'bg-primary text-white' : 'text-text-secondary hover:text-text'
              )}
            >
              <GitBranch className="h-3.5 w-3.5" /> Timeline
            </button>
          </div>
          {isLead && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary-dark transition-colors"
              title="Create a main task or sub-task"
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
          projectId={id ?? ''}
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
          projectId={id ?? ''}
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
                  'rounded-lg border border-border bg-surface-alt/50 p-3',
                  STATUS_ACCENT[status]
                )}
              >
                <div className="flex items-center gap-2 mb-3 px-0.5">
                  <Icon className="h-4 w-4 text-text-secondary" />
                  <span className="text-sm font-semibold text-text">{STATUS_LABEL[status]}</span>
                  <span className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center rounded-full border border-border bg-white px-1.5 text-[10px] font-semibold text-text-secondary">
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
                    <div className="rounded-md border border-dashed border-border py-7 text-center text-xs text-text-secondary">
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

