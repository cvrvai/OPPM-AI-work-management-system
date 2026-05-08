import { cn, formatDate } from '@/lib/utils'
import type { Task } from '@/types'
import { Target, Pencil, ChevronRight, Trash2 } from 'lucide-react'
import { PRIORITY_COLORS, STATUS_BADGE, STATUS_LABEL, NEXT_STATUS } from './constants'

export function TableView({
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
      <div className="rounded-lg border border-dashed border-border py-14 text-center text-sm text-text-secondary">
        No tasks yet. Click <span className="font-medium text-primary">+ Add Task</span> to get started.
      </div>
    )
  }

  const orderedTasks = (() => {
    const mainTasks = tasks.filter(t => !t.parent_task_id)
    const subByParent = new Map<string, Task[]>()
    for (const t of tasks) {
      if (t.parent_task_id) {
        const arr = subByParent.get(t.parent_task_id) ?? []
        arr.push(t)
        subByParent.set(t.parent_task_id, arr)
      }
    }
    if (mainTasks.length === 0 && tasks.length > 0) return tasks.map(t => ({ task: t, isSub: false }))
    const result: { task: Task; isSub: boolean }[] = []
    for (const mt of mainTasks) {
      result.push({ task: mt, isSub: false })
      for (const st of subByParent.get(mt.id) ?? []) {
        result.push({ task: st, isSub: true })
      }
    }
    for (const t of tasks) {
      if (t.parent_task_id && !mainTasks.find(m => m.id === t.parent_task_id)) {
        if (!result.find(r => r.task.id === t.id)) {
          result.push({ task: t, isSub: true })
        }
      }
    }
    return result
  })()

  return (
    <div className="rounded-lg border border-border bg-white overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-alt/80">
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
            {orderedTasks.map(({ task, isSub }, index) => (
              <tr
                key={task.id}
                className={cn(
                  'border-b border-border last:border-0 hover:bg-blue-50/30 transition-colors',
                  isSub ? 'bg-gray-50/40' : 'bg-white'
                )}
              >
                <td className="px-4 py-3 text-xs text-text-secondary">{index + 1}</td>
                <td className="px-4 py-3 max-w-[220px]">
                  <button
                    onClick={() => onEdit(task)}
                    className={cn(
                      'text-left transition-colors line-clamp-1 w-full',
                      isSub
                        ? 'pl-5 text-text-secondary hover:text-primary font-normal'
                        : 'font-semibold text-text hover:text-primary'
                    )}
                  >
                    {isSub && <span className="text-gray-300 mr-1">└</span>}
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
                    <div className="flex-1 h-1.5 rounded-full bg-surface-alt overflow-hidden">
                      <div className="h-full rounded-full bg-text-secondary" style={{ width: `${task.progress}%` }} />
                    </div>
                    <span className="text-xs font-medium text-text-secondary w-8 text-right shrink-0">{task.progress}%</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  {task.oppm_objective_id && objectiveMap.get(task.oppm_objective_id) ? (
                    <span className="inline-flex items-center gap-1 rounded bg-surface-alt border border-border px-1.5 py-0.5 text-[11px] font-medium text-text-secondary whitespace-nowrap">
                      <Target className="h-3 w-3 shrink-0" />
                      <span className="truncate max-w-[100px]">{objectiveMap.get(task.oppm_objective_id)}</span>
                    </span>
                  ) : (
                    <span className="text-gray-300 text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {task.assignee_id && memberMap.get(task.assignee_id) ? (
                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-alt border border-border text-[10px] font-bold text-text-secondary">
                        {(memberMap.get(task.assignee_id) ?? '?')[0].toUpperCase()}
                      </span>
                      <span className="text-xs text-text-secondary truncate max-w-[80px]">{memberMap.get(task.assignee_id)}</span>
                    </span>
                  ) : (
                    <span className="text-gray-300 text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
                  {task.start_date ? formatDate(task.start_date) : <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
                  {task.due_date ? formatDate(task.due_date) : <span className="text-gray-300">—</span>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => onEdit(task)} title="Edit" className="rounded p-1 text-text-secondary hover:bg-surface-alt hover:text-text transition-colors">
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => onStatusChange(task)} title={`Move to ${STATUS_LABEL[NEXT_STATUS[task.status]]}`} className="rounded p-1 text-text-secondary hover:bg-surface-alt hover:text-text transition-colors">
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => onDelete(task)} title="Delete" className="rounded p-1 text-text-secondary hover:bg-surface-alt hover:text-danger transition-colors">
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
