import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { Project, Priority } from '@/types'
import { cn, getStatusColor, formatDate } from '@/lib/utils'
import {
  Plus,
  Search,
  FolderKanban,
  Calendar,
  ArrowRight,
  X,
  Loader2,
} from 'lucide-react'

export function Projects() {
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      if (ws) {
        const res = await api.get<{ items: Project[]; total: number }>(`${wsPath}/projects`)
        return (res as any)?.items ?? []
      }
      return api.get<Project[]>('/projects')
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: Partial<Project>) =>
      ws ? api.post<Project>(`${wsPath}/projects`, data) : api.post<Project>('/projects', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCreate(false)
    },
  })

  const filtered = (projects || []).filter((p: Project) =>
    p.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Projects</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Manage your OPPM projects with AI-powered tracking
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          <Plus className="h-4 w-4" /> New Project
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
        <input
          type="text"
          placeholder="Search projects..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-border bg-white py-2 pl-10 pr-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
      </div>

      {/* Project Grid */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <FolderKanban className="h-12 w-12 text-text-secondary/30 mb-3" />
          <p className="text-sm text-text-secondary">
            {search ? 'No projects match your search' : 'No projects yet. Create your first project to get started.'}
          </p>
        </div>
      ) : (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="group rounded-xl border border-border bg-white p-5 shadow-sm hover:shadow-md hover:border-primary/30 transition-all"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                  <FolderKanban className="h-4.5 w-4.5 text-primary" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text group-hover:text-primary transition-colors">
                    {project.title}
                  </h3>
                  <span
                    className={cn(
                      'inline-block rounded-full px-2 py-0.5 text-[10px] font-medium mt-0.5',
                      getStatusColor(project.status)
                    )}
                  >
                    {project.status.replace('_', ' ')}
                  </span>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>

            <p className="text-xs text-text-secondary line-clamp-2 mb-4">
              {project.description}
            </p>

            {/* Progress Bar */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-secondary">Progress</span>
                <span className="text-xs font-semibold text-text">{project.progress}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${project.progress}%` }}
                />
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center gap-3 text-xs text-text-secondary">
              {project.start_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  Start: {formatDate(project.start_date)}
                </div>
              )}
              {project.deadline && (
                <div className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  Due: {formatDate(project.deadline)}
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          loading={createMutation.isPending}
        />
      )}
    </div>
  )
}

function CreateProjectModal({
  onClose,
  onSubmit,
  loading,
}: {
  onClose: () => void
  onSubmit: (data: Partial<Project>) => void
  loading: boolean
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [startDate, setStartDate] = useState('')
  const [deadline, setDeadline] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      title,
      description,
      priority,
      status: 'planning',
      progress: 0,
      start_date: startDate || null,
      deadline: deadline || null,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-xl border border-border bg-white p-6 shadow-lg space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">New Project</h2>
          <button type="button" onClick={onClose} className="text-text-secondary hover:text-text">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Deadline</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-alt"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading || !title}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </form>
    </div>
  )
}
