import { useState } from 'react'
import type React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatStore } from '@/stores/chatStore'
import { useChatContext } from '@/hooks/useChatContext'
import type { PaginatedResponse, Project, Priority, Methodology, WorkspaceMember } from '@/types'
import { cn, getStatusColor, formatDate } from '@/lib/utils'
import {
  Check,
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
  User,
} from 'lucide-react'

interface CreateProjectPayload {
  title: string
  description: string
  project_code: string | null
  objective_summary: string | null
  priority: Priority
  methodology: Methodology
  status: Project['status']
  progress: number
  start_date: string | null
  deadline: string | null
  end_date: string | null
  budget: number
  planning_hours: number
  lead_id: string | null
}

interface UpdateProjectPayload {
  title: string
  description: string
  project_code: string | null
  objective_summary: string | null
  status: Project['status']
  priority: Priority
  start_date: string | null
  deadline: string | null
  end_date: string | null
  budget: number
  planning_hours: number
  lead_id: string | null
}

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
  const openChat = useChatStore((s) => s.open)
  const addChatMessage = useChatStore((s) => s.addMessage)

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      const res = await api.get<PaginatedResponse<Project>>(`${wsPath}/projects`)
      return res.items ?? []
    },
    enabled: !!ws,
  })

  const { data: members = [] } = useQuery<WorkspaceMember[]>({
    queryKey: ['members', ws?.id],
    queryFn: () => api.get<WorkspaceMember[]>(`${wsPath}/members`),
    enabled: !!ws,
  })

  const createMutation = useMutation({
    mutationFn: async ({ data, memberAssignments }: { data: CreateProjectPayload; memberAssignments: { userId: string; role: string }[] }) => {
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
    mutationFn: ({ id, data }: { id: string; data: UpdateProjectPayload }) =>
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
          onClick={() => {
            setShowCreate(true)
            openChat()
            addChatMessage({
              role: 'assistant',
              content: `**Creating a new project — let me help you set it up!**\n\nBefore filling the form, here's a quick guide to the **Methodology** field:\n\n- 🔄 **Agile** — Iterative sprints (1–4 weeks). Best for software, R&D, or evolving requirements.\n- 📋 **Waterfall** — Sequential phases (Plan → Design → Build → Test → Deploy). Best for construction, compliance, or fixed-scope work.\n- 🔀 **Hybrid** — Waterfall milestones with Agile sprints inside. Best for large projects needing both structure and flexibility.\n- 🎯 **OPPM** — One-page targeted focus. Best for concise, outcome-driven initiatives across any industry.\n\nYou can also ask me to **create the project for you** — just describe what you want to build and I'll ask about methodology, objectives, deliverables, and timeline before setting it up.`,
            })
          }}
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

const fieldLabelClass = 'mb-1.5 block text-sm font-medium text-text-secondary'
const inputClass = 'w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10'
const selectClass = 'w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10'
const textareaClass = 'w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10 resize-none'
const sectionClass = ''
const sectionEyebrowClass = 'text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary'
const modalShellClass = 'flex max-h-[92vh] w-[min(58rem,calc(100vw-1rem))] flex-col overflow-hidden rounded-2xl border border-border bg-white shadow-2xl'
const secondaryButtonClass = 'rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-alt'
const primaryButtonClass = 'inline-flex items-center justify-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50'

function getMemberLabel(member: WorkspaceMember) {
  return member.display_name || member.email || member.user_id.slice(0, 8)
}

function CreateProjectModal({
  members,
  onClose,
  onSubmit,
  loading,
}: {
  members: WorkspaceMember[]
  onClose: () => void
  onSubmit: (data: CreateProjectPayload, memberAssignments: { userId: string; role: string }[]) => void
  loading: boolean
}) {
  const [step, setStep] = useState<1 | 2>(1)

  // Step 1 state
  const [title, setTitle] = useState('')
  const [projectCode, setProjectCode] = useState('')
  const [description, setDescription] = useState('')
  const [objectiveSummary, setObjectiveSummary] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [methodology, setMethodology] = useState<Methodology>('oppm')
  const [startDate, setStartDate] = useState('')
  const [deadline, setDeadline] = useState('')
  const [endDate, setEndDate] = useState('')
  const [budget, setBudget] = useState('')
  const [planningHours, setPlanningHours] = useState('')
  // Step 2 state: map from workspace_member.id → role
  const [assignments, setAssignments] = useState<Record<string, ProjectRole>>({})

  const selectedMembers = members.filter((member) => assignments[member.id])
  // Lead is whoever is assigned the 'lead' role in Step 2
  const leadEntry = Object.entries(assignments).find(([, role]) => role === 'lead')
  const selectedLead = leadEntry ? members.find((m) => m.id === leadEntry[0]) : undefined

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
    const payload: CreateProjectPayload = {
      title,
      description,
      project_code: projectCode || null,
      objective_summary: objectiveSummary || null,
      priority,
      methodology,
      status: 'planning',
      progress: 0,
      start_date: startDate || null,
      deadline: deadline || null,
      end_date: endDate || null,
      budget: budget ? Number(budget) : 0,
      planning_hours: planningHours ? Number(planningHours) : 0,
      lead_id: leadEntry ? leadEntry[0] : null,
    }
    onSubmit(payload, memberAssignments)
  }

  const selectedCount = selectedMembers.length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className={modalShellClass} onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className={sectionEyebrowClass}>Create a project</p>
              <h2 className="text-lg font-semibold text-text">New Project</h2>
              <p className="text-sm text-text-secondary">
                Start with the project brief, then confirm the team that should help deliver it.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          </div>

          {/* Stepper */}
          <div className="flex items-center gap-0 pb-4">
            {/* Step 1 */}
            <button
              type="button"
              onClick={() => setStep(1)}
              className="flex items-center gap-2.5 text-sm font-medium transition-colors"
            >
              <span className={cn(
                'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors',
                step === 1 ? 'bg-primary text-white' : 'bg-primary/10 text-primary'
              )}>
                1
              </span>
              <span className={step === 1 ? 'text-text font-semibold' : 'text-text-secondary'}>
                Project Brief
              </span>
            </button>

            {/* Connector */}
            <div className="mx-3 h-px flex-1 bg-border" />

            {/* Step 2 */}
            <button
              type="button"
              disabled={!title.trim()}
              onClick={() => title.trim() && setStep(2)}
              className="flex items-center gap-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed"
            >
              <span className={cn(
                'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors',
                step === 2
                  ? 'bg-primary text-white'
                  : title.trim()
                    ? 'bg-primary/10 text-primary'
                    : 'bg-slate-100 text-slate-400'
              )}>
                {selectedCount > 0 && step !== 2 ? (
                  <Check className="h-3.5 w-3.5" />
                ) : '2'}
              </span>
              <span className={cn(
                step === 2 ? 'text-text font-semibold' : title.trim() ? 'text-text-secondary' : 'text-slate-400'
              )}>
                Team Setup
                {selectedCount > 0 && (
                  <span className="ml-1.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                    {selectedCount}
                  </span>
                )}
              </span>
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6">
          {step === 1 ? (
            <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">
              {/* Left column — form fields */}
              <div className="xl:col-span-3">

                {/* Section: Project details */}
                <div className="pb-4 mb-3 border-b border-border">
                  <h3 className="mb-3 text-sm font-semibold text-text">Project details</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div className="md:col-span-2">
                      <label className={fieldLabelClass}>Project Name <span className="text-red-500">*</span></label>
                      <input
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        required
                        placeholder="e.g. FY2026 platform rollout"
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className={fieldLabelClass}>Project Code</label>
                      <input
                        value={projectCode}
                        onChange={(e) => setProjectCode(e.target.value)}
                        placeholder="e.g. PRJ-204"
                        maxLength={50}
                        className={inputClass}
                      />
                    </div>
                  </div>

                  <div className="mt-3">
                    <label className={fieldLabelClass}>Objective Summary</label>
                    <input
                      value={objectiveSummary}
                      onChange={(e) => setObjectiveSummary(e.target.value)}
                      placeholder="One clear sentence about the project outcome"
                      className={inputClass}
                    />
                  </div>

                  <div className="mt-3">
                    <label className={fieldLabelClass}>Description</label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={2}
                      placeholder="Add context, delivery notes, and success criteria"
                      className={textareaClass}
                    />
                  </div>
                </div>

                {/* Section: Schedule */}
                <div className="pb-4 mb-3 border-b border-border">
                  <h3 className="mb-3 text-sm font-semibold text-text">Schedule</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div>
                      <label className={fieldLabelClass}>Start Date</label>
                      <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputClass} />
                    </div>
                    <div>
                      <label className={fieldLabelClass}>Deadline</label>
                      <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={inputClass} />
                    </div>
                    <div>
                      <label className={fieldLabelClass}>End Date</label>
                      <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={inputClass} />
                    </div>
                  </div>
                </div>

                {/* Section: Resources & ownership */}
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-text">Resources &amp; ownership</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <label className={fieldLabelClass}>Budget</label>
                      <div className="relative">
                        <DollarSign className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={budget}
                          onChange={(e) => setBudget(e.target.value)}
                          placeholder="e.g. 50,000"
                          className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10"
                        />
                      </div>
                    </div>
                    <div>
                      <label className={fieldLabelClass}>Planning Hours</label>
                      <div className="relative">
                        <Clock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                        <input
                          type="number"
                          min="0"
                          step="0.5"
                          value={planningHours}
                          onChange={(e) => setPlanningHours(e.target.value)}
                          placeholder="e.g. 120"
                          className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-3">
                    <label className={fieldLabelClass}>Priority</label>
                    <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)} className={selectClass}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>

                  <div className="mt-3">
                    <label className={fieldLabelClass}>Methodology</label>
                    <select value={methodology} onChange={(e) => setMethodology(e.target.value as Methodology)} className={selectClass}>
                      <option value="oppm">OPPM</option>
                      <option value="agile">Agile</option>
                      <option value="waterfall">Waterfall</option>
                      <option value="hybrid">Hybrid (All)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Right column — snapshot sidebar */}
              <div className="mt-6 space-y-5 xl:col-span-2 xl:mt-0">

                {/* Planning snapshot card */}
                <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">Preview</p>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-text">{title.trim() || 'Untitled project'}</p>
                      <p className="mt-1 text-xs text-text-secondary line-clamp-2">
                        {objectiveSummary.trim() || 'No objective summary yet.'}
                      </p>
                    </div>
                    <span className="shrink-0 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      Planning
                    </span>
                  </div>

                  <div className="mt-4 divide-y divide-border text-sm">
                    <div className="flex items-center justify-between gap-3 py-2">
                      <span className="text-text-secondary">Leader</span>
                      <span className="font-medium text-text">{selectedLead ? getMemberLabel(selectedLead) : <span className="text-slate-400">Unassigned</span>}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 py-2">
                      <span className="text-text-secondary">Priority</span>
                      <span className={cn(
                        'rounded-md px-2 py-0.5 text-xs font-semibold capitalize',
                        priority === 'critical' ? 'bg-red-100 text-red-700' :
                        priority === 'high' ? 'bg-orange-100 text-orange-700' :
                        priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-slate-100 text-slate-600'
                      )}>{priority}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 py-2">
                      <span className="text-text-secondary">Budget</span>
                      <span className="font-medium text-text">{budget ? `$${Number(budget).toLocaleString()}` : <span className="text-slate-400">—</span>}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 py-2">
                      <span className="text-text-secondary">Planning Hours</span>
                      <span className="font-medium text-text">{planningHours ? `${planningHours} h` : <span className="text-slate-400">—</span>}</span>
                    </div>
                  </div>
                </div>

                {/* What happens next */}
                <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3.5">
                  <p className="mb-2 text-xs font-semibold text-blue-700">Step 2 — Team Setup</p>
                  <ul className="space-y-1.5 text-xs text-blue-600">
                    <li className="flex items-start gap-1.5"><span className="mt-px shrink-0">•</span>Pick which workspace members join this project.</li>
                    <li className="flex items-start gap-1.5"><span className="mt-px shrink-0">•</span>Assign each member a role (lead, contributor, reviewer, observer).</li>
                    <li className="flex items-start gap-1.5"><span className="mt-px shrink-0">•</span>The project starts in <strong>Planning</strong> and can be refined later.</li>
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">

              {/* Member list */}
              <div className="xl:col-span-3">
                <h3 className="mb-4 text-sm font-semibold text-text">Choose members and assign roles</h3>

                {members.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-gray-200 py-10 text-center">
                    <User className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                    <p className="text-sm text-text-secondary">No workspace members found.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {members.map((member) => {
                      const selected = !!assignments[member.id]
                      return (
                        <div
                          key={member.id}
                          onClick={() => toggleMember(member.id)}
                          className={cn(
                            'flex flex-col gap-3 rounded-lg border px-4 py-3.5 cursor-pointer transition-colors sm:flex-row sm:items-center',
                            selected
                              ? 'border-primary/40 bg-primary/5 shadow-sm'
                              : 'border-border bg-white hover:border-primary/20 hover:bg-surface-alt'
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              'flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-colors',
                              selected ? 'border-primary bg-primary text-white' : 'border-slate-300 bg-white text-transparent'
                            )}>
                              <Check className="h-3 w-3" />
                            </div>
                            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                              {getMemberLabel(member).charAt(0).toUpperCase()}
                            </div>
                          </div>

                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-text">{getMemberLabel(member)}</p>
                            <p className="text-xs text-text-secondary">
                              {member.email || 'No email on file'}
                              <span className="mx-1.5 text-slate-300">•</span>
                              <span className="capitalize">Workspace {member.role}</span>
                            </p>
                          </div>

                          {selected && (
                            <select
                              value={assignments[member.id]}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                e.stopPropagation()
                                setMemberRole(member.id, e.target.value as ProjectRole)
                              }}
                              className="w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm font-medium outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 sm:w-40"
                            >
                              {PROJECT_ROLES.map((role) => (
                                <option key={role} value={role}>{ROLE_LABEL[role]}</option>
                              ))}
                            </select>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Right sidebar */}
              <div className="mt-6 space-y-5 xl:col-span-2 xl:mt-0">

                {/* Team summary card */}
                <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Selected team</p>
                    <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                      {title.trim() || 'Untitled project'}
                    </span>
                  </div>
                  <p className="mb-3 text-sm font-semibold text-text">{selectedCount} member{selectedCount === 1 ? '' : 's'} selected</p>

                  <div className="space-y-1.5">
                    {selectedMembers.length === 0 ? (
                      <p className="text-sm text-text-secondary">No members selected yet. Select teammates from the list.</p>
                    ) : (
                      selectedMembers.map((member) => (
                        <div key={member.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
                          <span className="min-w-0 truncate font-medium text-text">{getMemberLabel(member)}</span>
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                            {ROLE_LABEL[assignments[member.id]]}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Role guide */}
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">Role guide</p>
                  <div className="space-y-1.5 text-sm text-text-secondary">
                    <div className="rounded-lg border border-border bg-white px-3.5 py-2.5"><strong className="text-text">Lead</strong> — owns delivery and major decisions.</div>
                    <div className="rounded-lg border border-border bg-white px-3.5 py-2.5"><strong className="text-text">Contributor</strong> — does the main execution work.</div>
                    <div className="rounded-lg border border-border bg-white px-3.5 py-2.5"><strong className="text-text">Reviewer</strong> — validates quality and approvals.</div>
                    <div className="rounded-lg border border-border bg-white px-3.5 py-2.5"><strong className="text-text">Observer</strong> — stays informed, no delivery duties.</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 border-t border-border bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-sm font-semibold text-text">
              {step === 1 ? 'Start with the project brief' : 'Confirm the team before creating'}
            </p>
            <p className="text-xs text-text-secondary">
              {step === 1
                ? 'A title unlocks the team step and gives the project a usable shell.'
                : `The project will be created in planning${selectedCount > 0 ? ` with ${selectedCount} team member${selectedCount === 1 ? '' : 's'}` : ''}.`}
            </p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button type="button" onClick={onClose} className={secondaryButtonClass}>Cancel</button>
            {step === 2 && (
              <button type="button" onClick={() => setStep(1)} className={secondaryButtonClass}>Back</button>
            )}
            {step === 1 ? (
              <button
                type="button"
                disabled={!title.trim()}
                onClick={() => setStep(2)}
                className={primaryButtonClass}
              >
                Next: Team Setup
              </button>
            ) : (
              <button type="button" disabled={loading} onClick={handleSubmit} className={primaryButtonClass}>
                {loading ? 'Creating...' : `Create Project${selectedCount > 0 ? ` (+${selectedCount})` : ''}`}
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
  onSubmit: (data: UpdateProjectPayload) => void
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
  const selectedLead = members.find((member) => member.id === leadId)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload: UpdateProjectPayload = {
      title,
      description,
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
    }
    onSubmit(payload)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <form
        onSubmit={handleSubmit}
        className={modalShellClass}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className={sectionEyebrowClass}>Update planning details</p>
              <h2 className="text-lg font-semibold text-text">Edit Project</h2>
              <p className="text-sm text-text-secondary">
                Refine the schedule, planning inputs, and leadership details without leaving the projects list.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          </div>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6">
          <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">
            <div className="xl:col-span-3">
              <section className="pb-4 mb-3 border-b border-border">
                <h3 className="mb-3 text-sm font-semibold text-text">Project details</h3>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="md:col-span-2">
                    <label className={fieldLabelClass}>Project Name *</label>
                    <input value={title} onChange={(e) => setTitle(e.target.value)} required className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Project Code</label>
                    <input value={projectCode} onChange={(e) => setProjectCode(e.target.value)} maxLength={50} className={inputClass} />
                  </div>
                </div>

                <div className="mt-3">
                  <label className={fieldLabelClass}>Objective Summary</label>
                  <input value={objectiveSummary} onChange={(e) => setObjectiveSummary(e.target.value)} placeholder="One-line project objective" className={inputClass} />
                </div>

                <div className="mt-3">
                  <label className={fieldLabelClass}>Description</label>
                  <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={textareaClass} />
                </div>
              </section>

              <section className="pb-4 mb-3 border-b border-border">
                <h3 className="mb-3 text-sm font-semibold text-text">Schedule</h3>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div>
                    <label className={fieldLabelClass}>Start Date</label>
                    <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Deadline</label>
                    <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>End Date</label>
                    <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={inputClass} />
                  </div>
                </div>
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-text">Resources &amp; ownership</h3>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Budget</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={budget}
                        onChange={(e) => setBudget(e.target.value)}
                        placeholder="e.g. 50,000"
                        className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10"
                      />
                    </div>
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Planning Hours</label>
                    <div className="relative">
                      <Clock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={planningHours}
                        onChange={(e) => setPlanningHours(e.target.value)}
                        placeholder="e.g. 120"
                        className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10"
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div>
                    <label className={fieldLabelClass}>Status</label>
                    <select value={status} onChange={(e) => setStatus(e.target.value as Project['status'])} className={selectClass}>
                      <option value="planning">Planning</option>
                      <option value="in_progress">In Progress</option>
                      <option value="on_hold">On Hold</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Priority</label>
                    <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)} className={selectClass}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Project Leader</label>
                    <select value={leadId} onChange={(e) => setLeadId(e.target.value)} className={selectClass}>
                      <option value="">— Unassigned —</option>
                      {members.map((member) => (
                        <option key={member.id} value={member.id}>
                          {getMemberLabel(member)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>
            </div>

            <div className="mt-6 space-y-5 xl:col-span-2 xl:mt-0">

              {/* Preview card */}
              <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">Preview</p>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">{title.trim() || 'Untitled project'}</p>
                    <p className="mt-1 text-xs text-text-secondary line-clamp-2">
                      {objectiveSummary.trim() || 'No objective summary yet.'}
                    </p>
                  </div>
                  <span className={cn('shrink-0 rounded-md px-2 py-0.5 text-xs font-medium', getStatusColor(status))}>
                    {status.replace('_', ' ')}
                  </span>
                </div>
                <div className="mt-4 divide-y divide-border text-sm">
                  <div className="flex items-center justify-between gap-3 py-2">
                    <span className="text-text-secondary">Leader</span>
                    <span className="font-medium text-text">{selectedLead ? getMemberLabel(selectedLead) : <span className="text-slate-400">Unassigned</span>}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 py-2">
                    <span className="text-text-secondary">Priority</span>
                    <span className={cn(
                      'rounded-md px-2 py-0.5 text-xs font-semibold capitalize',
                      priority === 'critical' ? 'bg-red-100 text-red-700' :
                      priority === 'high' ? 'bg-orange-100 text-orange-700' :
                      priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-slate-100 text-slate-600'
                    )}>{priority}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 py-2">
                    <span className="text-text-secondary">Budget</span>
                    <span className="font-medium text-text">{budget ? `$${Number(budget).toLocaleString()}` : <span className="text-slate-400">—</span>}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 py-2">
                    <span className="text-text-secondary">Planning Hours</span>
                    <span className="font-medium text-text">{planningHours ? `${planningHours} h` : <span className="text-slate-400">—</span>}</span>
                  </div>
                </div>
              </div>

              {/* Editing note */}
              <div className="rounded-lg border border-amber-100 bg-amber-50 px-4 py-3.5">
                <p className="mb-1.5 text-xs font-semibold text-amber-700">Editing note</p>
                <p className="text-xs text-amber-600">Tasks, OPPM entries, and memberships are unaffected. Only planning fields are updated here.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-border bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-sm font-semibold text-text">Save the updated project plan</p>
            <p className="text-xs text-text-secondary">The edit keeps the current project shell intact while refreshing its planning details.</p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button type="button" onClick={onClose} className={secondaryButtonClass}>Cancel</button>
            <button type="submit" disabled={loading || !title.trim()} className={primaryButtonClass}>
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
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
