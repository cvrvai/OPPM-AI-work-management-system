import { useState } from 'react'
import type React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listProjectsRouteApiV1WorkspacesWorkspaceIdProjectsGet,
  listMembersApiV1WorkspacesWorkspaceIdMembersGet,
  createProjectRouteApiV1WorkspacesWorkspaceIdProjectsPost,
  addProjectMemberRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdMembersPost,
  updateProjectRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPut,
  deleteProjectRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdDelete,
} from '@/generated/workspace-api/sdk.gen'
import type { ProjectCreate, ProjectUpdate } from '@/generated/workspace-api/types.gen'
import { updateEntityInCache } from '@/lib/utils/queryNormalizer'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatStore } from '@/stores/chatStore'
import { useToastStore } from '@/stores/toastStore'
import { useChatContext } from '@/hooks/useChatContext'
import type { PaginatedResponse, Project, Priority, Methodology, WorkspaceMember } from '@/types'
import { cn, getStatusColor, formatDate } from '@/lib/utils'
import {
  Plus,
  Search,
  FolderKanban,
  Calendar,
  ArrowRight,
  Loader2,
  MoreVertical,
  Pencil,
  Trash2,
} from 'lucide-react'
import { CreateProjectModal } from './projects/CreateProjectModal'
import { EditProjectModal } from './projects/EditProjectModal'
import { DeleteProjectDialog } from './projects/DeleteProjectDialog'

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
  const [optimisticDeletingId, setOptimisticDeletingId] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  useChatContext('workspace')
  const openChat = useChatStore((s) => s.open)
  const addChatMessage = useChatStore((s) => s.addMessage)

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      const res = await listProjectsRouteApiV1WorkspacesWorkspaceIdProjectsGet({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
      })
      const data = res.data as PaginatedResponse<Project>
      return data.items ?? []
    },
    enabled: !!ws,
    staleTime: 5 * 60 * 1000,
    placeholderData: (previousData) => previousData, // Keep previous workspace data visible while loading new one
  })

  const { data: members = [] } = useQuery<WorkspaceMember[]>({
    queryKey: ['members', ws?.id],
    queryFn: () =>
      listMembersApiV1WorkspacesWorkspaceIdMembersGet({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
      }).then((res) => (res.data ?? []) as WorkspaceMember[]),
    enabled: !!ws,
    staleTime: 5 * 60 * 1000,
    placeholderData: (previousData) => previousData,
  })

  const createMutation = useMutation({
    mutationFn: async ({ data, memberAssignments }: { data: CreateProjectPayload; memberAssignments: { userId: string; role: string }[] }) => {
      const res = await createProjectRouteApiV1WorkspacesWorkspaceIdProjectsPost({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
        body: data as unknown as ProjectCreate,
      })
      const project = res.data as Project
      if (memberAssignments.length > 0) {
        await Promise.allSettled(
          memberAssignments.map(({ userId, role }) =>
            addProjectMemberRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdMembersPost({
              client: workspaceClient,
              path: { workspace_id: ws!.id, project_id: project.id },
              body: { user_id: userId, role },
            })
          )
        )
      }
      return project
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCreate(false)
      addToast('Project created successfully', 'success')
    },
    onError: () => {
      addToast('Failed to create project. Please try again.', 'error')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProjectPayload }) =>
      updateProjectRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPut({
        client: workspaceClient,
        path: { workspace_id: ws!.id, project_id: id },
        body: data as unknown as ProjectUpdate,
      }).then((res) => res.data as Project),
    onSuccess: (updatedProject) => {
      updateEntityInCache(queryClient, updatedProject, [['projects']])
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setEditingProject(null)
      addToast('Project updated successfully', 'success')
    },
    onError: () => {
      addToast('Failed to update project. Please try again.', 'error')
    },
  })

  const addToast = useToastStore((s) => s.addToast)

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      deleteProjectRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdDelete({
        client: workspaceClient,
        path: { workspace_id: ws!.id, project_id: id },
      }).then((res) => res.data),
    onMutate: async (deletedId) => {
      setOptimisticDeletingId(deletedId)
      await queryClient.cancelQueries({ queryKey: ['projects', ws?.id] })
      const previous = queryClient.getQueryData<Project[]>(['projects', ws?.id])
      queryClient.setQueryData(['projects', ws?.id], (old: Project[] | undefined) =>
        old?.filter((p) => p.id !== deletedId)
      )
      return { previous }
    },
    onError: (_err, _deletedId, context) => {
      setOptimisticDeletingId(null)
      if (context?.previous) {
        queryClient.setQueryData(['projects', ws?.id], context.previous)
      }
      addToast('Failed to delete project. Please try again.', 'error')
    },
    onSuccess: () => {
      setOptimisticDeletingId(null)
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setDeletingProject(null)
      addToast('Project deleted successfully', 'success')
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
          className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark transition-colors"
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
          className="w-full rounded-md border border-border bg-white py-2 pl-10 pr-3 text-sm outline-none focus:border-text-secondary focus:ring-1 focus:ring-text-secondary/20"
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
            className={cn(
              'group relative rounded-lg border border-border bg-white hover:bg-surface-alt/40 transition-all duration-300',
              optimisticDeletingId === project.id && 'opacity-50 scale-95 pointer-events-none'
            )}
          >
            <Link to={`/projects/${project.id}`} className="block p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-surface-alt border border-border">
                    <FolderKanban className="h-4 w-4 text-text-secondary" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text group-hover:text-text transition-colors pr-6">
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

              <p className="text-xs text-text-secondary line-clamp-2 mb-3">
                {project.description}
              </p>

              {/* Progress Bar */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-text-secondary">Progress</span>
                  <span className="text-xs font-medium text-text">{project.progress}%</span>
                </div>
                <div className="h-1 w-full rounded-full bg-surface-alt">
                  <div
                    className="h-full rounded-full bg-text-secondary transition-all"
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
