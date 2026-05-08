import type { Project } from '@/types'
import { X } from 'lucide-react'

export function DeleteProjectDialog({
  project,
  onClose,
  onConfirm,
  loading,
}: {
  project: Project
  onClose: () => void
  onConfirm: () => void
  loading: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl border border-border bg-white p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-red-600">Delete Project</h2>
          <button type="button" onClick={onClose} className="text-text-secondary hover:text-text"><X className="h-5 w-5" /></button>
        </div>
        <p className="text-sm text-text-secondary">
          Are you sure you want to delete{' '}
          <span className="font-semibold text-text">{project.title}</span>? This will permanently
          remove all objectives, tasks, timeline entries, and costs.
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-alt">Cancel</button>
          <button onClick={onConfirm} disabled={loading} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50">{loading ? 'Deleting...' : 'Delete Project'}</button>
        </div>
      </div>
    </div>
  )
}
