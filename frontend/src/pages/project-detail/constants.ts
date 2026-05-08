import type { Priority, TaskStatus } from '@/types'
import { Clock, Target, CheckCircle2 } from 'lucide-react'

export const PRIORITY_COLORS: Record<Priority, string> = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

export const PRIORITY_BORDER: Record<Priority, string> = {
  low: 'border-l-slate-300',
  medium: 'border-l-blue-400',
  high: 'border-l-amber-400',
  critical: 'border-l-red-500',
}

export const STATUS_ACCENT: Record<TaskStatus, string> = {
  todo: 'border-t-slate-400',
  in_progress: 'border-t-blue-500',
  completed: 'border-t-emerald-500',
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  completed: 'Completed',
}

export const STATUS_BADGE: Record<TaskStatus, string> = {
  todo: 'bg-slate-100 text-slate-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-emerald-100 text-emerald-700',
}

export const STATUS_ICONS = {
  todo: Clock,
  in_progress: Target,
  completed: CheckCircle2,
}

export const NEXT_STATUS: Record<TaskStatus, TaskStatus> = {
  todo: 'in_progress',
  in_progress: 'completed',
  completed: 'todo',
}
