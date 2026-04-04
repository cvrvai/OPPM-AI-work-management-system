import { useState } from 'react'
import type React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatContext } from '@/hooks/useChatContext'
import type { Project, Priority, WorkspaceMember } from '@/types'
import { cn, getStatusColor, formatDate } from '@/lib/utils'
import {
  Plus,
  Search,
  FolderKanban,
  Calendar,
  ArrowRight,
  X,
  Loader2,
  MoreVertical,
  Pencil,
  Trash2,
  DollarSign,
  Clock,
  Hash,
  User,
} from 'lucide-react'

export function Projects() {
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [deletingProject, setDeletingProject] = useState<Project | null>(null)
  const [menuOpen, setMenuOpen] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  useChatContext('workspace')

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      const res = await api.get<{ items: Project[]; total: number }>(`${wsPath}/projects`)
      return (res as any)?.items ?? []
    },
    enabled: !!ws,
  })

  const { data: members = [] } = useQuery<WorkspaceMember[]>({
    queryKey: ['members', ws?.id],
    queryFn: () => api.get<WorkspaceMember[]>(`${wsPath}/members`),
    enabled: !!ws,
  })

  const createMutation = useMutation({
    mutationFn: async ({ data, memberAssignments }: { data: Partial<Project>; memberAssignments: { userId: string; role: string }[] }) => {
      const project = await api.post<Project>(`${wsPath}/projects`, data)
      // Add selected members to the project (best-effort, parallel)
      if (memberAssignments.length > 0) {
        await Promise.allSettled(
          memberAssignments.map(({ userId, role }) =>
            api.post(`${wsPath}/projects/${project.id}/members`, { user_id: userId, role })
          )
        )
      }
      return project
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCreate(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Project> }) =>
      api.put<Project>(`${wsPath}/projects/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setEditingProject(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`${wsPath}/projects/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setDeletingProject(null)
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
          <div
            key={project.id}
            className="group relative rounded-xl border border-border bg-white shadow-sm hover:shadow-md hover:border-primary/30 transition-all"
          >
            <Link to={`/projects/${project.id}`} className="block p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                    <FolderKanban className="h-4.5 w-4.5 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text group-hover:text-primary transition-colors pr-6">
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
                <ArrowRight className="h-4 w-4 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
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

            {/* Kebab menu */}
            <div className="absolute top-3 right-3">
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setMenuOpen(menuOpen === project.id ? null : project.id)
                }}
                className="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary hover:bg-surface-alt hover:text-text transition-colors"
              >
                <MoreVertical className="h-4 w-4" />
              </button>
              {menuOpen === project.id && (
                <div
                  className="absolute right-0 top-8 z-10 w-36 rounded-lg border border-border bg-white py-1 shadow-lg"
                  onMouseLeave={() => setMenuOpen(null)}
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditingProject(project)
                      setMenuOpen(null)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-text hover:bg-surface-alt"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Edit
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setDeletingProject(project)
                      setMenuOpen(null)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <CreateProjectModal
          members={members}
          onClose={() => setShowCreate(false)}
          onSubmit={(data, memberAssignments) => createMutation.mutate({ data, memberAssignments })}
          loading={createMutation.isPending}
        />
      )}

      {/* Edit Modal */}
      {editingProject && (
        <EditProjectModal
          project={editingProject}
          members={members}
          onClose={() => setEditingProject(null)}
          onSubmit={(data) => updateMutation.mutate({ id: editingProject.id, data })}
          loading={updateMutation.isPending}
        />
      )}

      {/* Delete Confirm */}
      {deletingProject && (
        <DeleteProjectDialog
          project={deletingProject}
          onClose={() => setDeletingProject(null)}
          onConfirm={() => deleteMutation.mutate(deletingProject.id)}
          loading={deleteMutation.isPending}
        />
      )}
    </div>
  )
}

const PROJECT_ROLES = ['lead', 'contributor', 'reviewer', 'observer'] as const
type ProjectRole = typeof PROJECT_ROLES[number]

const ROLE_LABEL: Record<ProjectRole, string> = {
  lead: 'Lead',
  contributor: 'Contributor',
  reviewer: 'Reviewer',
  observer: 'Observer',
}

function CreateProjectModal({
  members,
  onClose,
  onSubmit,
  loading,
}: {
  members: WorkspaceMember[]
  onClose: () => void
  onSubmit: (data: Partial<Project>, memberAssignments: { userId: string; role: string }[]) => void
  loading: boolean
}) {
  const [step, setStep] = useState<1 | 2>(1)

  // Step 1 state
  const [title, setTitle] = useState('')
  const [projectCode, setProjectCode] = useState('')
  const [description, setDescription] = useState('')
  const [objectiveSummary, setObjectiveSummary] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [startDate, setStartDate] = useState('')
  const [deadline, setDeadline] = useState('')
  const [endDate, setEndDate] = useState('')
  const [budget, setBudget] = useState('')
  const [planningHours, setPlanningHours] = useState('')
  const [leadId, setLeadId] = useState('')

  // Step 2 state: map from workspace_member.id → role
  const [assignments, setAssignments] = useState<Record<string, ProjectRole>>({})

  const toggleMember = (memberId: string) => {
    setAssignments((prev) => {
      if (prev[memberId]) {
        const next = { ...prev }
        delete next[memberId]
        return next
      }
      return { ...prev, [memberId]: 'contributor' }
    })
  }

  const setMemberRole = (memberId: string, role: ProjectRole) => {
    setAssignments((prev) => ({ ...prev, [memberId]: role }))
  }

  const handleSubmit = () => {
    const memberAssignments = Object.entries(assignments).map(([userId, role]) => ({ userId, role }))
    onSubmit(
      {
        title,
        description: description || null,
        project_code: projectCode || null,
        objective_summary: objectiveSummary || null,
        priority,
        status: 'planning',
        progress: 0,
        start_date: startDate || null,
        deadline: deadline || null,
        end_date: endDate || null,
        budget: budget ? Number(budget) : 0,
        planning_hours: planningHours ? Number(planningHours) : 0,
        lead_id: leadId || null,
      } as any,
      memberAssignments
    )
  }

  const selectedCount = Object.keys(assignments).length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-lg max-h-[90vh] flex flex-col rounded-xl border border-border bg-white shadow-lg">

        {/* Modal header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold">New Project</h2>
            {/* Step indicator */}
            <div className="flex items-center gap-2 mt-1.5">
              <button
                type="button"
                onClick={() => setStep(1)}
                className={cn(
                  'flex items-center gap-1.5 text-xs font-medium rounded-full px-2.5 py-0.5 transition-colors',
                  step === 1
                    ? 'bg-primary text-white'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                )}
              >
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white/20 text-[10px] font-bold">1</span>
                Project Info
              </button>
              <span className="text-slate-300">›</span>
              <button
                type="button"
                disabled={!title}
                onClick={() => title && setStep(2)}
                className={cn(
                  'flex items-center gap-1.5 text-xs font-medium rounded-full px-2.5 py-0.5 transition-colors',
                  step === 2
                    ? 'bg-primary text-white'
                    : !title
                    ? 'bg-slate-100 text-slate-300 cursor-not-allowed'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                )}
              >
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white/20 text-[10px] font-bold">2</span>
                Team
                {selectedCount > 0 && (
                  <span className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-white/30 text-[10px] font-bold">
                    {selectedCount}
                  </span>
                )}
              </button>
            </div>
          </div>
          <button type="button" onClick={onClose} className="text-text-secondary hover:text-text">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 px-6 py-5">
          {step === 1 && (
            <div className="space-y-5">
              {/* Basic Info */}
              <fieldset className="space-y-3">
                <legend className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Hash className="h-3.5 w-3.5" /> Basic Information
                </legend>
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-text-secondary mb-1">Project Name *</label>
                    <input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      required
                      placeholder="e.g. FY2025 System Migration"
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Project Code</label>
                    <input
                      value={projectCode}
                      onChange={(e) => setProjectCode(e.target.value)}
                      placeholder="e.g. PRJ-001"
                      maxLength={50}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-1">Objective Summary</label>
                  <input
                    value={objectiveSummary}
                    onChange={(e) => setObjectiveSummary(e.target.value)}
                    placeholder="One-line project objective"
                    className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={2}
                    placeholder="Detailed project description..."
                    className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 resize-none"
                  />
                </div>
              </fieldset>

              {/* Schedule */}
              <fieldset className="space-y-3">
                <legend className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" /> Schedule
                </legend>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Start Date</label>
                    <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Deadline</label>
                    <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">End Date</label>
                    <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                  </div>
                </div>
              </fieldset>

              {/* Resources */}
              <fieldset className="space-y-3">
                <legend className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5" /> Resources &amp; Assignment
                </legend>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Budget</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                      <input type="number" min="0" step="0.01" value={budget} onChange={(e) => setBudget(e.target.value)}
                        placeholder="0.00"
                        className="w-full rounded-lg border border-border pl-8 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Planning Hours</label>
                    <div className="relative">
                      <Clock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                      <input type="number" min="0" step="0.5" value={planningHours} onChange={(e) => setPlanningHours(e.target.value)}
                        placeholder="0"
                        className="w-full rounded-lg border border-border pl-8 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Priority</label>
                    <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary">
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Project Leader</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                      <select value={leadId} onChange={(e) => setLeadId(e.target.value)}
                        className="w-full rounded-lg border border-border pl-8 pr-3 py-2 text-sm outline-none focus:border-primary">
                        <option value="">-- Select --</option>
                        {members.map((m) => (
                          <option key={m.user_id} value={m.user_id}>
                            {m.display_name || m.email || m.user_id.slice(0, 8)}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </fieldset>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-text-secondary">
                Select members to add to this project and assign their role.
                <span className="text-text font-medium"> {selectedCount} selected.</span>
              </p>
              {members.length === 0 ? (
                <p className="text-sm text-text-secondary italic text-center py-6">No workspace members found.</p>
              ) : (
                <div className="space-y-2">
                  {members.map((m) => {
                    const selected = !!assignments[m.id]
                    return (
                      <div
                        key={m.id}
                        onClick={() => toggleMember(m.id)}
                        className={cn(
                          'flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors',
                          selected
                            ? 'border-primary/40 bg-primary/5'
                            : 'border-border hover:border-primary/20 hover:bg-surface-alt'
                        )}
                      >
                        {/* Checkbox */}
                        <div className={cn(
                          'flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-colors',
                          selected ? 'bg-primary border-primary' : 'border-slate-300'
                        )}>
                          {selected && <span className="text-white text-[10px] font-bold leading-none">✓</span>}
                        </div>

                        {/* Avatar */}
                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                          {(m.display_name || m.email || '?').charAt(0).toUpperCase()}
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-text truncate">
                            {m.display_name || m.email?.split('@')[0] || 'Member'}
                          </p>
                          {m.email && <p className="text-xs text-text-secondary truncate">{m.email}</p>}
                        </div>

                        {/* Role selector — only clickable when selected */}
                        {selected && (
                          <select
                            value={assignments[m.id]}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              e.stopPropagation()
                              setMemberRole(m.id, e.target.value as ProjectRole)
                            }}
                            className="rounded-lg border border-border bg-white px-2 py-1 text-xs font-medium outline-none focus:border-primary"
                          >
                            {PROJECT_ROLES.map((r) => (
                              <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border flex-shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-alt"
          >
            Cancel
          </button>
          <div className="flex items-center gap-2">
            {step === 2 && (
              <button
                type="button"
                onClick={() => setStep(1)}
                className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-alt"
              >
                ← Back
              </button>
            )}
            {step === 1 ? (
              <button
                type="button"
                disabled={!title}
                onClick={() => setStep(2)}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50"
              >
                Next: Add Team →
              </button>
            ) : (
              <button
                type="button"
                disabled={loading}
                onClick={handleSubmit}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50"
              >
                {loading ? 'Creating...' : `Create Project${selectedCount > 0 ? ` (+${selectedCount} members)` : ''}`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function EditProjectModal({
  project,
  members,
  onClose,
  onSubmit,
  loading,
}: {
  project: Project
  members: WorkspaceMember[]
  onClose: () => void
  onSubmit: (data: Partial<Project>) => void
  loading: boolean
}) {
  const [title, setTitle] = useState(project.title)
  const [projectCode, setProjectCode] = useState(project.project_code ?? '')
  const [description, setDescription] = useState(project.description ?? '')
  const [objectiveSummary, setObjectiveSummary] = useState(project.objective_summary ?? '')
  const [status, setStatus] = useState(project.status)
  const [priority, setPriority] = useState<Priority>(project.priority)
  const [startDate, setStartDate] = useState(project.start_date?.slice(0, 10) ?? '')
  const [deadline, setDeadline] = useState(project.deadline?.slice(0, 10) ?? '')
  const [endDate, setEndDate] = useState(project.end_date?.slice(0, 10) ?? '')
  const [budget, setBudget] = useState(project.budget ? String(project.budget) : '')
  const [planningHours, setPlanningHours] = useState(project.planning_hours ? String(project.planning_hours) : '')
  const [leadId, setLeadId] = useState(project.lead_id ?? '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      title,
      description: description || null,
      project_code: projectCode || null,
      objective_summary: objectiveSummary || null,
      status,
      priority,
      start_date: startDate || null,
      deadline: deadline || null,
      end_date: endDate || null,
      budget: budget ? Number(budget) : 0,
      planning_hours: planningHours ? Number(planningHours) : 0,
      lead_id: leadId || null,
    } as any)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-white p-6 shadow-lg space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Edit Project</h2>
          <button type="button" onClick={onClose} className="text-text-secondary hover:text-text">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Basic Info Section */}
        <fieldset className="space-y-3">
          <legend className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Hash className="h-3.5 w-3.5" /> Basic Information
          </legend>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-text-secondary mb-1">Project Name *</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Project Code</label>
              <input
                value={projectCode}
                onChange={(e) => setProjectCode(e.target.value)}
                maxLength={50}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Objective Summary</label>
            <input
              value={objectiveSummary}
              onChange={(e) => setObjectiveSummary(e.target.value)}
              placeholder="One-line project objective"
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 resize-none"
            />
          </div>
        </fieldset>

        {/* Schedule Section */}
        <fieldset className="space-y-3">
          <legend className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5" /> Schedule
          </legend>
          <div className="grid grid-cols-3 gap-3">
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
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>
        </fieldset>

        {/* Resources Section */}
        <fieldset className="space-y-3">
          <legend className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <DollarSign className="h-3.5 w-3.5" /> Resources &amp; Assignment
          </legend>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Budget</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-lg border border-border pl-8 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Planning Hours</label>
              <div className="relative">
                <Clock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={planningHours}
                  onChange={(e) => setPlanningHours(e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border border-border pl-8 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as Project['status'])}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="planning">Planning</option>
                <option value="in_progress">In Progress</option>
                <option value="on_hold">On Hold</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
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
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Project Leader</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                <select
                  value={leadId}
                  onChange={(e) => setLeadId(e.target.value)}
                  className="w-full rounded-lg border border-border pl-8 pr-3 py-2 text-sm outline-none focus:border-primary"
                >
                  <option value="">-- Select --</option>
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.display_name || m.email || m.user_id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </fieldset>

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
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  )
}

function DeleteProjectDialog({
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
          <button type="button" onClick={onClose} className="text-text-secondary hover:text-text">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-sm text-text-secondary">
          Are you sure you want to delete{' '}
          <span className="font-semibold text-text">{project.title}</span>? This will permanently
          remove all objectives, tasks, timeline entries, and costs.
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-alt"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? 'Deleting...' : 'Delete Project'}
          </button>
        </div>
      </div>
    </div>
  )
}
