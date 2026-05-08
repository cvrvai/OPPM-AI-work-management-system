import { cn, formatDate } from '@/lib/utils'
import type { Task } from '@/types'
import { Target, User, CalendarDays, ChevronRight, Trash2 } from 'lucide-react'
import { PRIORITY_COLORS, PRIORITY_BORDER, STATUS_LABEL, NEXT_STATUS } from './constants'

export function TaskCard({
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
        'group rounded-md border border-border bg-white p-3.5 hover:bg-surface-alt/40 transition-colors',
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
            <span className="inline-flex items-center gap-1 rounded bg-surface-alt border border-border px-1.5 py-0.5 text-[10px] font-medium text-text-secondary">
              <Target className="h-2.5 w-2.5" /> {objectiveName}
            </span>
          )}
          {ownerName && (
            <span className="inline-flex items-center gap-1 rounded bg-surface-alt border border-border px-1.5 py-0.5 text-[10px] font-medium text-text-secondary">
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
      <div className="mt-2 h-1.5 w-full rounded-full bg-surface-alt">
        <div
          className="h-full rounded-full transition-all bg-text-secondary"
          style={{ width: `${Math.max(task.progress, 0)}%` }}
        />
      </div>
    </div>
  )
}
