import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listPhasesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesGet,
  listPhaseDocumentsRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdDocumentsGet,
  updatePhaseRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdPut,
  approvePhaseRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdApprovePost,
  createPhaseDocumentRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdDocumentsPost,
  deletePhaseDocumentRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdDocumentsDocIdDelete,
} from '@/generated/workspace-api/sdk.gen'
import type { PhaseUpdate, PhaseDocumentCreate } from '@/generated/workspace-api/types.gen'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import type { ProjectPhase, PhaseDocument } from '@/types/waterfall'
import { cn } from '@/lib/utils'
import {
  ArrowLeft,
  Plus,
  X,
  Loader2,
  FileText,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Clock,
  Circle,
  Lock,
} from 'lucide-react'

const PHASE_LABELS: Record<string, string> = {
  requirements: 'Requirements',
  design: 'Design',
  development: 'Development',
  testing: 'Testing',
  deployment: 'Deployment',
  maintenance: 'Maintenance',
}

const PHASE_ICONS: Record<string, string> = {
  requirements: '📋',
  design: '🎨',
  development: '💻',
  testing: '🧪',
  deployment: '🚀',
  maintenance: '🔧',
}

const STATUS_STYLES: Record<string, { bg: string; icon: typeof Circle }> = {
  not_started: { bg: 'bg-slate-100 text-slate-600', icon: Circle },
  in_progress: { bg: 'bg-blue-100 text-blue-700', icon: Clock },
  completed: { bg: 'bg-amber-100 text-amber-700', icon: CheckCircle2 },
  approved: { bg: 'bg-emerald-100 text-emerald-700', icon: ShieldCheck },
}

const DOC_TYPE_LABELS: Record<string, string> = {
  srs: 'SRS',
  sdd: 'SDD',
  test_plan: 'Test Plan',
  release_notes: 'Release Notes',
  general: 'General',
}

export function WaterfallView() {
  useWorkspaceNavGuard()
  const { id: projectId } = useParams<{ id: string }>()
  const workspace = useWorkspaceStore((s) => s.currentWorkspace)
  const wsId = workspace?.id
  const queryClient = useQueryClient()

  const [expandedPhase, setExpandedPhase] = useState<string | null>(null)
  const [showCreateDoc, setShowCreateDoc] = useState<string | null>(null)

  // ── Phases Query ──
  const { data: phases, isLoading } = useQuery({
    queryKey: ['phases', wsId, projectId],
    queryFn: () =>
      listPhasesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesGet({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId! },
      }).then((res) => (res.data ?? []) as ProjectPhase[]),
    enabled: !!wsId && !!projectId,
  })

  const phaseList = phases ?? []

  // ── Phase Documents Query (per expanded phase) ──
  const { data: docsData } = useQuery({
    queryKey: ['phase-documents', wsId, projectId, expandedPhase],
    queryFn: () =>
      listPhaseDocumentsRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdDocumentsGet({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId!, phase_id: expandedPhase! },
      }).then((res) => res.data as { items: PhaseDocument[]; total: number }),
    enabled: !!wsId && !!projectId && !!expandedPhase,
  })

  const docs = docsData?.items ?? []

  // ── Mutations ──
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['phases', wsId, projectId] })
    if (expandedPhase) {
      queryClient.invalidateQueries({ queryKey: ['phase-documents', wsId, projectId, expandedPhase] })
    }
  }

  const updatePhaseMut = useMutation({
    mutationFn: ({ phaseId, data }: { phaseId: string; data: Record<string, unknown> }) =>
      updatePhaseRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdPut({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId!, phase_id: phaseId },
        body: data as unknown as PhaseUpdate,
      }).then((res) => res.data),
    onSuccess: invalidate,
  })

  const approvePhaseMut = useMutation({
    mutationFn: (phaseId: string) =>
      approvePhaseRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdApprovePost({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId!, phase_id: phaseId },
      }).then((res) => res.data),
    onSuccess: invalidate,
  })

  const createDocMut = useMutation({
    mutationFn: ({ phaseId, data }: { phaseId: string; data: Record<string, unknown> }) =>
      createPhaseDocumentRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdDocumentsPost({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId!, phase_id: phaseId },
        body: data as unknown as PhaseDocumentCreate,
      }).then((res) => res.data),
    onSuccess: () => { invalidate(); setShowCreateDoc(null) },
  })

  const deleteDocMut = useMutation({
    mutationFn: ({ phaseId, docId }: { phaseId: string; docId: string }) =>
      deletePhaseDocumentRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdPhasesPhaseIdDocumentsDocIdDelete({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId!, phase_id: phaseId, doc_id: docId },
      }).then((res) => res.data),
    onSuccess: invalidate,
  })

  const handleCreateDoc = (e: React.FormEvent<HTMLFormElement>, phaseId: string) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    createDocMut.mutate({
      phaseId,
      data: {
        title: fd.get('title'),
        content: fd.get('content') || '',
        document_type: fd.get('document_type') || 'general',
      },
    })
  }

  if (!wsId) return null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to={`/projects/${projectId}`} className="rounded-md border border-border p-2 hover:bg-surface-alt transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-text">Waterfall Phases</h1>
          <p className="text-sm text-text-secondary">Sequential phase gates with documentation</p>
        </div>
      </div>

      {/* Phase Pipeline Visualization */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : (
        <>
          {/* Pipeline bar */}
          <div className="flex items-center gap-1 rounded-lg border border-border bg-white p-3">
            {phaseList.map((phase, idx) => {
              const style = STATUS_STYLES[phase.status] ?? STATUS_STYLES.not_started
              const Icon = style.icon
              const isLast = idx === phaseList.length - 1
              return (
                <div key={phase.id} className="flex items-center flex-1">
                  <button
                    onClick={() => setExpandedPhase(expandedPhase === phase.id ? null : phase.id)}
                    className={cn(
                      'flex flex-1 items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors',
                      expandedPhase === phase.id ? 'ring-1 ring-border' : '',
                      style.bg,
                    )}
                  >
                    <span>{PHASE_ICONS[phase.phase_type]}</span>
                    <span className="truncate">{PHASE_LABELS[phase.phase_type]}</span>
                    <Icon className="ml-auto h-3.5 w-3.5 flex-shrink-0" />
                  </button>
                  {!isLast && <ChevronDown className="mx-1 h-3 w-3 rotate-[-90deg] text-text-secondary/50 flex-shrink-0" />}
                </div>
              )
            })}
          </div>

          {/* Phase Detail Cards */}
          <div className="space-y-3">
            {phaseList.map((phase) => {
              const isExpanded = expandedPhase === phase.id
              const style = STATUS_STYLES[phase.status] ?? STATUS_STYLES.not_started
              const canApprove = phase.status === 'in_progress' || phase.status === 'completed'

              return (
                <div key={phase.id} className="rounded-lg border border-border bg-white overflow-hidden">
                  <button
                    onClick={() => setExpandedPhase(isExpanded ? null : phase.id)}
                    className="flex w-full items-center justify-between p-4 text-left hover:bg-surface-alt transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{PHASE_ICONS[phase.phase_type]}</span>
                      <div>
                        <h3 className="font-semibold text-text">{PHASE_LABELS[phase.phase_type]}</h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase', style.bg)}>
                            {phase.status.replace('_', ' ')}
                          </span>
                          {phase.start_date && (
                            <span className="text-xs text-text-secondary">{phase.start_date} → {phase.end_date ?? '?'}</span>
                          )}
                          {phase.gate_approved_at && (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <ShieldCheck className="h-3 w-3" /> Gate approved
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    {isExpanded ? <ChevronUp className="h-4 w-4 text-text-secondary" /> : <ChevronDown className="h-4 w-4 text-text-secondary" />}
                  </button>

                  {isExpanded && (
                    <div className="border-t border-border p-4 space-y-4">
                      {/* Status controls */}
                      <div className="flex items-center gap-2">
                        <label className="text-sm font-medium text-text-secondary">Status:</label>
                        <select
                          value={phase.status}
                          onChange={(e) => updatePhaseMut.mutate({ phaseId: phase.id, data: { status: e.target.value } })}
                          className="rounded-md border border-border px-2 py-1 text-sm"
                          disabled={phase.status === 'approved'}
                        >
                          <option value="not_started">Not Started</option>
                          <option value="in_progress">In Progress</option>
                          <option value="completed">Completed</option>
                        </select>
                        {canApprove && (
                          <button
                            onClick={() => approvePhaseMut.mutate(phase.id)}
                            disabled={approvePhaseMut.isPending}
                          className="ml-2 flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
                          >
                            <ShieldCheck className="h-3.5 w-3.5" />
                            Approve Gate
                          </button>
                        )}
                        {phase.status === 'approved' && (
                          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600">
                            <Lock className="h-3 w-3" /> Locked
                          </span>
                        )}
                      </div>

                      {/* Phase notes */}
                      {phase.notes && (
                        <div className="rounded-md bg-surface-alt p-3 text-sm text-text-secondary">{phase.notes}</div>
                      )}

                      {/* Documents */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="text-sm font-semibold text-text">Documents ({docs.length})</h4>
                          <button
                            onClick={() => setShowCreateDoc(phase.id)}
                            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-surface-alt transition-colors"
                          >
                            <Plus className="h-3 w-3" /> Add Document
                          </button>
                        </div>
                        {docs.length === 0 ? (
                          <p className="text-xs text-text-secondary italic">No documents yet for this phase</p>
                        ) : (
                          <div className="space-y-2">
                            {docs.map((doc) => (
                              <div key={doc.id} className="flex items-center justify-between rounded-md border border-border p-3">
                                <div className="flex items-center gap-2">
                                  <FileText className="h-4 w-4 text-text-secondary" />
                                  <div>
                                    <span className="text-sm font-medium text-text">{doc.title}</span>
                                    <span className="ml-2 rounded bg-surface-alt px-1.5 py-0.5 text-[10px] font-medium text-text-secondary">
                                      {DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                                    </span>
                                    <span className="ml-1 text-[10px] text-text-secondary">v{doc.version}</span>
                                  </div>
                                </div>
                                <button
                                  onClick={() => deleteDocMut.mutate({ phaseId: phase.id, docId: doc.id })}
                                  className="text-red-400 hover:text-red-600 transition-colors"
                                >
                                  <X className="h-4 w-4" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Create Document Modal */}
      {showCreateDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={(e) => handleCreateDoc(e, showCreateDoc)} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">New Phase Document</h2>
              <button type="button" onClick={() => setShowCreateDoc(null)}><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium">Title *</label>
                <input name="title" required maxLength={300} placeholder="Document title" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Type</label>
                <select name="document_type" defaultValue="general" className="w-full rounded-md border border-border px-3 py-2 text-sm">
                  <option value="general">General</option>
                  <option value="srs">SRS (Software Requirements Specification)</option>
                  <option value="sdd">SDD (Software Design Document)</option>
                  <option value="test_plan">Test Plan</option>
                  <option value="release_notes">Release Notes</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Content</label>
                <textarea name="content" rows={6} placeholder="Markdown or plain text…" className="w-full rounded-md border border-border px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowCreateDoc(null)} className="rounded-md border border-border px-4 py-2 text-sm hover:bg-surface-alt">Cancel</button>
              <button type="submit" disabled={createDocMut.isPending} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
                {createDocMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
