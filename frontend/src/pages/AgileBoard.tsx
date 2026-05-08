import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import type { Epic, UserStory, Sprint, Retrospective, BurndownData } from '@/types/agile'
import { cn } from '@/lib/utils'
import {
  ArrowLeft,
  Plus,
  X,
  Loader2,
  BookOpen,
  Layers,
  IterationCw,
  Target,
  ChevronRight,
  CheckCircle2,
  Clock,
  AlertTriangle,
} from 'lucide-react'

type Tab = 'backlog' | 'sprints' | 'board'

const STORY_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-600',
  ready: 'bg-blue-100 text-blue-700',
  in_progress: 'bg-amber-100 text-amber-700',
  done: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-red-100 text-red-700',
}

const SPRINT_STATUS_COLORS: Record<string, string> = {
  planning: 'bg-slate-100 text-slate-600',
  active: 'bg-blue-100 text-blue-700',
  completed: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-red-100 text-red-700',
}

export function AgileBoard() {
  useWorkspaceNavGuard()
  const { id: projectId } = useParams<{ id: string }>()
  const workspace = useWorkspaceStore((s) => s.currentWorkspace)
  const wsId = workspace?.id
  const queryClient = useQueryClient()

  const [tab, setTab] = useState<Tab>('backlog')
  const [showCreateStory, setShowCreateStory] = useState(false)
  const [showCreateSprint, setShowCreateSprint] = useState(false)
  const [showCreateEpic, setShowCreateEpic] = useState(false)

  // ── Queries ──
  const base = `/v1/workspaces/${wsId}/projects/${projectId}`

  const { data: epicsData } = useQuery({
    queryKey: ['epics', wsId, projectId],
    queryFn: () => api.get<{ items: Epic[]; total: number }>(`${base}/epics`),
    enabled: !!wsId && !!projectId,
  })

  const { data: storiesData, isLoading: storiesLoading } = useQuery({
    queryKey: ['user-stories', wsId, projectId],
    queryFn: () => api.get<{ items: UserStory[]; total: number }>(`${base}/user-stories`),
    enabled: !!wsId && !!projectId,
  })

  const { data: sprintsData } = useQuery({
    queryKey: ['sprints', wsId, projectId],
    queryFn: () => api.get<{ items: Sprint[]; total: number }>(`${base}/sprints`),
    enabled: !!wsId && !!projectId,
  })

  const epics = epicsData?.items ?? []
  const stories = storiesData?.items ?? []
  const sprints = sprintsData?.items ?? []
  const backlogStories = stories.filter((s) => !s.sprint_id)

  // ── Mutations ──
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['user-stories', wsId, projectId] })
    queryClient.invalidateQueries({ queryKey: ['sprints', wsId, projectId] })
    queryClient.invalidateQueries({ queryKey: ['epics', wsId, projectId] })
  }

  const createStoryMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post(`${base}/user-stories`, data),
    onSuccess: () => { invalidate(); setShowCreateStory(false) },
  })

  const createSprintMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post(`${base}/sprints`, data),
    onSuccess: () => { invalidate(); setShowCreateSprint(false) },
  })

  const createEpicMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post(`${base}/epics`, data),
    onSuccess: () => { invalidate(); setShowCreateEpic(false) },
  })

  const startSprintMut = useMutation({
    mutationFn: (sprintId: string) => api.post(`${base}/sprints/${sprintId}/start`, {}),
    onSuccess: invalidate,
  })

  const completeSprintMut = useMutation({
    mutationFn: (sprintId: string) => api.post(`${base}/sprints/${sprintId}/complete`, {}),
    onSuccess: invalidate,
  })

  const updateStoryMut = useMutation({
    mutationFn: ({ storyId, data }: { storyId: string; data: Record<string, unknown> }) =>
      api.put(`${base}/user-stories/${storyId}`, data),
    onSuccess: invalidate,
  })

  // ── Handlers ──
  const handleCreateStory = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    createStoryMut.mutate({
      title: fd.get('title'),
      description: fd.get('description') || '',
      story_points: fd.get('story_points') ? Number(fd.get('story_points')) : null,
      priority: fd.get('priority') || 'medium',
    })
  }

  const handleCreateSprint = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    createSprintMut.mutate({
      name: fd.get('name'),
      goal: fd.get('goal') || null,
      sprint_number: sprints.length + 1,
      start_date: fd.get('start_date') || null,
      end_date: fd.get('end_date') || null,
    })
  }

  const handleCreateEpic = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    createEpicMut.mutate({
      title: fd.get('title'),
      description: fd.get('description') || '',
      priority: fd.get('priority') || 'medium',
    })
  }

  if (!wsId) return null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to={`/projects/${projectId}`} className="rounded-md border border-border p-2 hover:bg-surface-alt transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text">Agile Board</h1>
            <p className="text-sm text-text-secondary">Backlog, sprints & user stories</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-md bg-surface-alt p-1">
        {([
          { key: 'backlog' as Tab, label: 'Product Backlog', icon: BookOpen },
          { key: 'sprints' as Tab, label: 'Sprints', icon: IterationCw },
          { key: 'board' as Tab, label: 'Sprint Board', icon: Layers },
        ] as const).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
              tab === key ? 'bg-white text-text shadow-sm' : 'text-text-secondary hover:text-text',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Backlog Tab */}
      {tab === 'backlog' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Product Backlog ({backlogStories.length} stories)</h2>
            <div className="flex gap-2">
              <button onClick={() => setShowCreateEpic(true)} className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface-alt transition-colors">
                <Plus className="h-3.5 w-3.5" /> Epic
              </button>
              <button onClick={() => setShowCreateStory(true)} className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark transition-colors">
                <Plus className="h-3.5 w-3.5" /> User Story
              </button>
            </div>
          </div>

          {/* Epics summary */}
          {epics.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {epics.map((epic) => (
                <span key={epic.id} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1 text-xs font-medium">
                  <Target className="h-3 w-3 text-text-secondary" />
                  {epic.title}
                  <span className="text-text-secondary">
                    ({stories.filter((s) => s.epic_id === epic.id).length})
                  </span>
                </span>
              ))}
            </div>
          )}

          {storiesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : backlogStories.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-12 text-center">
              <BookOpen className="mx-auto h-12 w-12 text-text-secondary/40" />
              <h3 className="mt-4 text-lg font-semibold text-text">No stories yet</h3>
              <p className="mt-1 text-sm text-text-secondary">Create user stories to build your product backlog</p>
            </div>
          ) : (
            <div className="space-y-2">
              {backlogStories.map((story) => (
                <div key={story.id} className="flex items-center gap-3 rounded-md border border-border bg-white p-3 hover:bg-surface-alt transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-text truncate">{story.title}</h3>
                      <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase', STORY_STATUS_COLORS[story.status])}>
                        {story.status.replace('_', ' ')}
                      </span>
                    </div>
                    {story.description && (
                      <p className="mt-0.5 text-xs text-text-secondary line-clamp-1">{story.description}</p>
                    )}
                  </div>
                  {story.story_points !== null && (
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-alt border border-border text-xs font-bold text-text-secondary">
                      {story.story_points}
                    </span>
                  )}
                  {/* Assign to sprint dropdown */}
                  {sprints.length > 0 && (
                    <select
                      className="rounded-md border border-border px-2 py-1 text-xs"
                      value=""
                      onChange={(e) => {
                        if (e.target.value) {
                          updateStoryMut.mutate({ storyId: story.id, data: { sprint_id: e.target.value } })
                        }
                      }}
                    >
                      <option value="">Move to sprint…</option>
                      {sprints.filter((s) => s.status !== 'completed').map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sprints Tab */}
      {tab === 'sprints' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Sprints ({sprints.length})</h2>
            <button onClick={() => setShowCreateSprint(true)} className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark transition-colors">
              <Plus className="h-3.5 w-3.5" /> New Sprint
            </button>
          </div>

          {sprints.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-12 text-center">
              <IterationCw className="mx-auto h-12 w-12 text-text-secondary/40" />
              <h3 className="mt-4 text-lg font-semibold text-text">No sprints yet</h3>
              <p className="mt-1 text-sm text-text-secondary">Create your first sprint to start iterating</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sprints.map((sprint) => {
                const sprintStories = stories.filter((s) => s.sprint_id === sprint.id)
                const doneCount = sprintStories.filter((s) => s.status === 'done').length
                const totalPoints = sprintStories.reduce((sum, s) => sum + (s.story_points ?? 0), 0)
                return (
                  <div key={sprint.id} className="rounded-lg border border-border bg-white p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-surface-alt border border-border text-sm font-bold text-text-secondary">
                          {sprint.sprint_number}
                        </span>
                        <div>
                          <h3 className="font-semibold text-text">{sprint.name}</h3>
                          {sprint.goal && <p className="text-xs text-text-secondary">{sprint.goal}</p>}
                        </div>
                        <span className={cn('rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase', SPRINT_STATUS_COLORS[sprint.status])}>
                          {sprint.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {sprint.status === 'planning' && (
                          <button
                            onClick={() => startSprintMut.mutate(sprint.id)}
                            className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-dark transition-colors"
                          >
                            Start Sprint
                          </button>
                        )}
                        {sprint.status === 'active' && (
                          <button
                            onClick={() => completeSprintMut.mutate(sprint.id)}
                            className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-dark transition-colors"
                          >
                            Complete Sprint
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="mt-3 flex items-center gap-4 text-xs text-text-secondary">
                      <span>{sprintStories.length} stories</span>
                      <span>{doneCount} done</span>
                      <span>{totalPoints} pts</span>
                      {sprint.velocity !== null && <span className="font-medium text-emerald-600">Velocity: {sprint.velocity}</span>}
                      {sprint.start_date && <span>{sprint.start_date} → {sprint.end_date ?? '?'}</span>}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Sprint Board Tab */}
      {tab === 'board' && (() => {
        const activeSprint = sprints.find((s) => s.status === 'active')
        if (!activeSprint) {
          return (
            <div className="rounded-lg border border-dashed border-border p-12 text-center">
              <Layers className="mx-auto h-12 w-12 text-text-secondary/40" />
              <h3 className="mt-4 text-lg font-semibold text-text">No active sprint</h3>
              <p className="mt-1 text-sm text-text-secondary">Start a sprint to see the board view</p>
            </div>
          )
        }
        const sprintStories = stories.filter((s) => s.sprint_id === activeSprint.id)
        const columns: { key: string; label: string; icon: typeof Clock }[] = [
          { key: 'draft', label: 'Draft', icon: AlertTriangle },
          { key: 'ready', label: 'Ready', icon: Target },
          { key: 'in_progress', label: 'In Progress', icon: Clock },
          { key: 'done', label: 'Done', icon: CheckCircle2 },
        ]
        return (
          <div>
            <h2 className="mb-4 text-lg font-semibold">{activeSprint.name} — Sprint Board</h2>
            <div className="grid grid-cols-4 gap-4">
              {columns.map(({ key, label, icon: Icon }) => {
                const col = sprintStories.filter((s) => s.status === key)
                return (
                  <div key={key} className="rounded-lg border border-border bg-surface-alt/50 p-3">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-secondary">
                      <Icon className="h-4 w-4" />
                      {label} ({col.length})
                    </div>
                    <div className="space-y-2">
                      {col.map((story) => (
                        <div key={story.id} className="rounded-md border border-border bg-white p-3">
                          <h4 className="text-sm font-medium text-text">{story.title}</h4>
                          {story.story_points !== null && (
                            <span className="mt-1 inline-block rounded-full bg-surface-alt border border-border px-2 py-0.5 text-[10px] font-bold text-text-secondary">
                              {story.story_points} pts
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* Create Story Modal */}
      {showCreateStory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleCreateStory} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">New User Story</h2>
              <button type="button" onClick={() => setShowCreateStory(false)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium">Title *</label>
                <input name="title" required maxLength={300} placeholder="As a [user], I want [action] so that [benefit]" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Description</label>
                <textarea name="description" rows={3} placeholder="Detailed description…" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium">Story Points</label>
                  <input name="story_points" type="number" min={0} className="w-full rounded-md border border-border px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Priority</label>
                  <select name="priority" defaultValue="medium" className="w-full rounded-md border border-border px-3 py-2 text-sm">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowCreateStory(false)} className="rounded-md border border-border px-4 py-2 text-sm hover:bg-surface-alt">Cancel</button>
              <button type="submit" disabled={createStoryMut.isPending} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
                {createStoryMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Create Sprint Modal */}
      {showCreateSprint && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleCreateSprint} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">New Sprint</h2>
              <button type="button" onClick={() => setShowCreateSprint(false)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium">Sprint Name *</label>
                <input name="name" required maxLength={100} placeholder={`Sprint ${sprints.length + 1}`} className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Goal</label>
                <textarea name="goal" rows={2} placeholder="What should this sprint achieve?" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium">Start Date</label>
                  <input name="start_date" type="date" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">End Date</label>
                  <input name="end_date" type="date" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowCreateSprint(false)} className="rounded-md border border-border px-4 py-2 text-sm hover:bg-surface-alt">Cancel</button>
              <button type="submit" disabled={createSprintMut.isPending} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
                {createSprintMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Create Epic Modal */}
      {showCreateEpic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleCreateEpic} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">New Epic</h2>
              <button type="button" onClick={() => setShowCreateEpic(false)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium">Title *</label>
                <input name="title" required maxLength={200} placeholder="Epic name" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Description</label>
                <textarea name="description" rows={3} className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Priority</label>
                <select name="priority" defaultValue="medium" className="w-full rounded-md border border-border px-3 py-2 text-sm">
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowCreateEpic(false)} className="rounded-md border border-border px-4 py-2 text-sm hover:bg-surface-alt">Cancel</button>
              <button type="submit" disabled={createEpicMut.isPending} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
                {createEpicMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
