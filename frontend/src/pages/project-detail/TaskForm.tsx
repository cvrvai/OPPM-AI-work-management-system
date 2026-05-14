import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listTaskReportsRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsGet,
  createTaskReportRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsPost,
  approveTaskReportRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsReportIdApprovePatch,
  deleteTaskReportRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsReportIdDelete,
  createObjectiveRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmObjectivesPost,
} from '@/generated/workspace-api/sdk.gen'
import type { TaskReportCreate, TaskReportApprove } from '@/generated/workspace-api/types.gen'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { Task, TaskReport, OPPMObjective, OPPMSubObjective, WorkspaceMember, Priority, TaskStatus } from '@/types'
import { cn } from '@/lib/utils'
import { TaskOwnerEditor, type TaskOwnerAssignment } from '@/components/features/TaskOwnerEditor'
import {
  Loader2,
  Plus,
  X,
  Pencil,
  ClipboardList,
  CheckCircle,
  XCircle,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  GitBranch,
  Clock,
} from 'lucide-react'
import { STATUS_BADGE, STATUS_LABEL } from './constants'

export function TaskForm({
  title,
  initial,
  projectId,
  objectives,
  subObjectives = [],
  members,
  allMembers = [],
  allTasks = [],
  onSubmit,
  onCancel,
  isPending,
  wsPath,
  isLead = false,
  currentUserId = '',
}: {
  title: string
  initial?: Task
  projectId: string
  objectives: OPPMObjective[]
  subObjectives?: OPPMSubObjective[]
  members: WorkspaceMember[]
  allMembers?: { id: string; member_id: string; source: 'workspace' | 'virtual'; name: string; is_leader: boolean }[]
  allTasks?: Task[]
  onSubmit: (data: Record<string, unknown>) => void
  onCancel: () => void
  isPending: boolean
  wsPath: string
  isLead?: boolean
  currentUserId?: string
}) {
  const queryClient = useQueryClient()
  const workspace = useWorkspaceStore((s) => s.currentWorkspace)
  const wsId = workspace?.id
  const [tab, setTab] = useState<'details' | 'reports'>('details')
  const [reportForm, setReportForm] = useState({ report_date: new Date().toISOString().slice(0, 10), hours: '', description: '' })
  const [showReportForm, setShowReportForm] = useState(false)
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [manualObjectiveTitle, setManualObjectiveTitle] = useState('')
  const [createdObjectives, setCreatedObjectives] = useState<OPPMObjective[]>([])
  const [objectiveNotice, setObjectiveNotice] = useState<string | null>(null)
  const [showObjectiveCreator, setShowObjectiveCreator] = useState(false)
  const initialSubObjectiveIds = (((initial as unknown as Record<string, unknown>)?.sub_objective_ids as string[] | undefined) ?? [])
  const initialVirtualAssignees = initial?.virtual_assignees?.map((virtualAssignee) => virtualAssignee.virtual_member_id) ?? []
  const initialOwnerAssignments = (initial?.owners ?? [])
    .filter((owner): owner is TaskOwnerAssignment => owner.priority === 'A' || owner.priority === 'B' || owner.priority === 'C')
    .map((owner) => ({ member_id: owner.member_id, priority: owner.priority }))

  const reportsQuery = useQuery<TaskReport[]>({
    queryKey: ['task-reports', initial?.id],
    queryFn: () =>
      listTaskReportsRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsGet({
        client: workspaceClient,
        path: { workspace_id: wsId!, task_id: initial!.id },
      }).then((res) => (res.data ?? []) as TaskReport[]),
    enabled: !!initial && tab === 'reports' && !!wsId,
  })

  const addReport = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createTaskReportRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsPost({
        client: workspaceClient,
        path: { workspace_id: wsId!, task_id: initial!.id },
        body: data as unknown as TaskReportCreate,
      }).then((res) => res.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['task-reports', initial?.id] }); setReportForm({ report_date: new Date().toISOString().slice(0, 10), hours: '', description: '' }); setShowReportForm(false) },
  })

  const approveReport = useMutation({
    mutationFn: ({ reportId, is_approved }: { reportId: string; is_approved: boolean }) =>
      approveTaskReportRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsReportIdApprovePatch({
        client: workspaceClient,
        path: { workspace_id: wsId!, task_id: initial!.id, report_id: reportId },
        body: { is_approved } as TaskReportApprove,
      }).then((res) => res.data as TaskReport),
    onSuccess: (updated) => {
      queryClient.setQueryData<TaskReport[]>(
        ['task-reports', initial?.id],
        (old) => old ? old.map((r) => r.id === updated.id ? updated : r) : old,
      )
    },
  })

  const deleteReport = useMutation({
    mutationFn: (reportId: string) =>
      deleteTaskReportRouteApiV1WorkspacesWorkspaceIdTasksTaskIdReportsReportIdDelete({
        client: workspaceClient,
        path: { workspace_id: wsId!, task_id: initial!.id, report_id: reportId },
      }).then((res) => res.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task-reports', initial?.id] }),
  })

  const createObjective = useMutation({
    mutationFn: (objectiveTitle: string) =>
      createObjectiveRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmObjectivesPost({
        client: workspaceClient,
        path: { workspace_id: wsId!, project_id: projectId },
        body: { title: objectiveTitle },
      }).then((res) => res.data as OPPMObjective),
    onSuccess: (objective) => {
      const normalizedObjective: OPPMObjective = { ...objective, tasks: objective.tasks ?? [] }
      setCreatedObjectives((prev) =>
        prev.some((item) => item.id === normalizedObjective.id) ? prev : [...prev, normalizedObjective]
      )
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', projectId] })
      setForm((current) => ({ ...current, oppm_objective_id: normalizedObjective.id }))
      setManualObjectiveTitle('')
      setShowObjectiveCreator(false)
      setObjectiveNotice(`Created and linked objective "${normalizedObjective.title}".`)
    },
    onError: (error: Error) => { setObjectiveNotice(error.message) },
  })

  const [form, setForm] = useState({
    title: initial?.title || '',
    description: initial?.description || '',
    priority: initial?.priority || 'medium',
    status: initial?.status || 'todo',
    progress: initial?.progress ?? 0,
    project_contribution: initial?.project_contribution ?? 0,
    start_date: initial?.start_date || '',
    due_date: initial?.due_date || '',
    oppm_objective_id: initial?.oppm_objective_id || '',
    assignee_id: initial?.assignee_id || '',
    parent_task_id: initial?.parent_task_id || '',
  })
  const [dependsOn, setDependsOn] = useState<string[]>(initial?.depends_on ?? [])
  const [subObjIds, setSubObjIds] = useState<string[]>(initialSubObjectiveIds)
  const [virtualAssignees, setVirtualAssignees] = useState<string[]>(initialVirtualAssignees)
  const [ownerAssignments, setOwnerAssignments] = useState<TaskOwnerAssignment[]>(initialOwnerAssignments)
  const [showAdvancedOwners, setShowAdvancedOwners] = useState(initialOwnerAssignments.length > 0)
  const [showDependencies, setShowDependencies] = useState((initial?.depends_on?.length ?? 0) > 0)
  const [showSubObjectives, setShowSubObjectives] = useState(initialSubObjectiveIds.length > 0)
  const [showVirtualAssignees, setShowVirtualAssignees] = useState(initialVirtualAssignees.length > 0)

  const workspaceMemberById = new Map(members.map((member) => [member.id, member]))
  const workspaceMemberByUserId = new Map(members.map((member) => [member.user_id, member]))
  const projectAllMemberById = new Map(allMembers.map((member) => [member.id, member]))
  const projectAllMemberByWorkspaceMemberId = new Map(
    allMembers
      .filter((member) => member.source === 'workspace')
      .map((member) => [member.member_id, member]),
  )
  const mainTaskOptions = allTasks.filter((task) => !task.parent_task_id && task.id !== initial?.id)
  const virtualMemberOptions = allMembers.filter((member) => member.source === 'virtual')

  const toggleDependency = (taskId: string) => {
    setDependsOn((prev) => prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId])
  }

  const toggleSubObj = (soId: string) => {
    setSubObjIds((prev) => prev.includes(soId) ? prev.filter((id) => id !== soId) : [...prev, soId])
  }

  const toggleVirtualAssignee = (vmId: string) => {
    setVirtualAssignees((prev) => prev.includes(vmId) ? prev.filter((id) => id !== vmId) : [...prev, vmId])
  }

  const handleOwnerAssignmentsChange = (nextAssignments: TaskOwnerAssignment[]) => {
    setOwnerAssignments(nextAssignments)
    const primaryOwner = nextAssignments.find((assignment) => assignment.priority === 'A')
    if (!primaryOwner) {
      return
    }
    const projectAllMember = projectAllMemberById.get(primaryOwner.member_id)
    if (!projectAllMember || projectAllMember.source !== 'workspace') {
      return
    }
    const workspaceMember = workspaceMemberById.get(projectAllMember.member_id)
    if (!workspaceMember) {
      return
    }
    setForm((current) => ({ ...current, assignee_id: workspaceMember.user_id }))
  }

  const availableObjectives = [
    ...objectives,
    ...createdObjectives.filter((created) => !objectives.some((objective) => objective.id === created.id)),
  ]

  const getMissingPillars = () => {
    const missing: string[] = []
    if (!form.oppm_objective_id) missing.push('Objective')
    if (!form.assignee_id) missing.push('Owner')
    if (!form.due_date) missing.push('Due date')
    return missing
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitAttempted(true)
    if (!form.title.trim()) return
    const nextMissingPillars = getMissingPillars()
    if (nextMissingPillars.length > 0) {
      if (!form.oppm_objective_id && availableObjectives.length === 0) {
        setShowObjectiveCreator(true)
      }
      return
    }
    const data: Record<string, unknown> = {
      ...form,
      depends_on: dependsOn,
      sub_objective_ids: subObjIds,
      virtual_assignees: virtualAssignees,
      oppm_owner_assignments: ownerAssignments,
    }
    if (!data.start_date) delete data.start_date
    if (!data.due_date) delete data.due_date
    if (!data.oppm_objective_id) delete data.oppm_objective_id
    if (!data.assignee_id) delete data.assignee_id
    if (!data.parent_task_id) delete data.parent_task_id
    if (virtualAssignees.length === 0) delete data.virtual_assignees
    if (!initial) {
      delete data.status
      if (data.progress === 0) delete data.progress
    }
    if (subObjIds.length === 0) delete data.sub_objective_ids
    onSubmit(data)
  }

  const missingPillars = getMissingPillars()
  const isOppmAligned = missingPillars.length === 0
  const selectedObjective = availableObjectives.find((objective) => objective.id === form.oppm_objective_id)
  const selectedOwner = members.find((member) => member.user_id === form.assignee_id)
  const showRequiredState = submitAttempted && !isOppmAligned
  const objectiveMissing = showRequiredState && !form.oppm_objective_id
  const ownerMissing = showRequiredState && !form.assignee_id
  const dueDateMissing = showRequiredState && !form.due_date
  const footerTitle = isOppmAligned
    ? 'Ready to save'
    : submitAttempted
      ? 'Fix required fields above'
      : 'Required: Objective, Owner, Due Date'
  const footerMessage = isOppmAligned
    ? 'This task has the core OPPM fields in place.'
    : submitAttempted
      ? 'This task cannot be saved until the highlighted required fields are completed.'
      : 'These three fields are required before the task can be created.'
  const formatCompactDate = (value: string | null | undefined) => {
    if (!value) return null
    const date = new Date(`${value}T00:00:00`)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  }
  const currentTaskLabel = initial?.title?.trim() || 'Untitled task'
  const parentTask = form.parent_task_id ? allTasks.find((task) => task.id === form.parent_task_id) : undefined
  const ownerSummary = selectedOwner?.display_name || selectedOwner?.email || (form.assignee_id ? form.assignee_id.slice(0, 8) : '')
  const dueDateSummary = formatCompactDate(form.due_date)
  const reportsCount = reportsQuery.data?.length ?? 0
  const totalLoggedHours = reportsQuery.data ? reportsQuery.data.reduce((sum, report) => sum + report.hours, 0).toFixed(1) : '0.0'
  const headerEyebrow = initial ? 'Edit existing task' : 'Add execution details'
  const headerDescription = initial
    ? 'Review status, ownership, dates, and execution history for this task.'
    : 'Keep the task brief clear, link it to the right objective, and set ownership without crowding the form.'
  const briefEyebrow = initial ? 'Task details' : 'Task brief'
  const briefTitle = initial ? 'Update the task scope and notes' : 'What needs to get done?'
  const deliveryTitle = initial ? 'Review current progress and workflow state' : 'Schedule, progress, and workflow state'

  const fieldLabelClass = 'mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-text-secondary'
  const inputClass = 'w-full rounded-xl border border-border bg-white px-3.5 py-2.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10'
  const selectClass = 'w-full rounded-xl border border-border bg-white px-3.5 py-2.5 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10'
  const textareaClass = 'w-full rounded-xl border border-border bg-white px-3.5 py-2.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10 resize-none'
  const sectionClass = 'rounded-2xl border border-border bg-surface-alt/70 p-3.5 sm:p-4'
  const sectionEyebrowClass = 'text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary'
  const disclosureButtonClass = 'flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-white px-3.5 py-2.5 text-left transition-colors hover:bg-surface-alt'
  const requiredFieldClass = 'border-red-300 bg-red-50/40 focus:border-red-500 focus:ring-red-100'
  const summaryPillClass = 'inline-flex items-center gap-1 rounded-full border border-border bg-white px-2.5 py-1 text-xs font-medium text-text'
  const summaryAlertPillClass = 'inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onCancel}>
      <form
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-[min(100%-1rem,72rem)] flex-col overflow-hidden rounded-[1.75rem] border border-border bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-3 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">{headerEyebrow}</p>
              <h3 className="text-lg font-semibold text-text">{title}</h3>
              {initial && <p className="text-sm font-medium text-text">Editing "{currentTaskLabel}"</p>}
              <p className="text-sm text-text-secondary">{headerDescription}</p>
            </div>
            <button type="button" onClick={onCancel} className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
              <X className="h-4.5 w-4.5" />
            </button>
          </div>
          {initial && (
            <div className="space-y-3 pb-3">
              <div className="inline-flex max-w-full items-center gap-1 rounded-2xl border border-border bg-surface-alt/70 p-1">
                <button type="button" onClick={() => setTab('details')} className={cn('flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors', tab === 'details' ? 'bg-white text-text shadow-sm ring-1 ring-border' : 'text-text-secondary hover:text-text')}>
                  <Pencil className="h-3.5 w-3.5" /> Task Details
                </button>
                <button type="button" onClick={() => setTab('reports')} className={cn('flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors', tab === 'reports' ? 'bg-white text-text shadow-sm ring-1 ring-border' : 'text-text-secondary hover:text-text')}>
                  <ClipboardList className="h-3.5 w-3.5" /> Daily Reports
                  {reportsQuery.data && reportsQuery.data.length > 0 && (
                    <span className="ml-1 rounded-full bg-surface-alt px-1.5 py-0.5 text-[10px] font-bold text-slate-600 ring-1 ring-slate-200">{reportsQuery.data.length}</span>
                  )}
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold', STATUS_BADGE[form.status])}>{STATUS_LABEL[form.status]}</span>
                <span className={summaryPillClass}>{form.progress}% progress</span>
                <span className={summaryPillClass}>{parentTask ? 'Sub-task' : 'Main task'}</span>
                <span className={ownerSummary ? summaryPillClass : summaryAlertPillClass}>{ownerSummary ? `Owner: ${ownerSummary}` : 'Owner required'}</span>
                <span className={dueDateSummary ? summaryPillClass : summaryAlertPillClass}>{dueDateSummary ? `Due: ${dueDateSummary}` : 'Due date required'}</span>
                <span className={form.oppm_objective_id ? summaryPillClass : summaryAlertPillClass}>{form.oppm_objective_id ? 'Objective linked' : 'Objective required'}</span>
              </div>
            </div>
          )}
        </div>

        {tab === 'reports' && initial ? (
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="rounded-2xl border border-border bg-surface-alt/70 px-3.5 py-3">
                <p className={sectionEyebrowClass}>Task history</p>
                <h4 className="mt-1 text-sm font-semibold text-text">Review execution updates and daily reports</h4>
                <div className="mt-2 flex flex-wrap gap-2">
                  <span className={summaryPillClass}>{reportsCount} report{reportsCount === 1 ? '' : 's'}</span>
                  <span className={summaryPillClass}>{totalLoggedHours}h logged</span>
                  <span className={ownerSummary ? summaryPillClass : summaryAlertPillClass}>{ownerSummary ? `Owner: ${ownerSummary}` : 'Unassigned'}</span>
                </div>
              </div>
              {(!initial?.assignee_id || initial.assignee_id === currentUserId) && (
                <button type="button" onClick={() => setShowReportForm(v => !v)} className="inline-flex items-center justify-center gap-1 rounded-xl bg-primary px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark">
                  <Plus className="h-3.5 w-3.5" /> Log Report
                </button>
              )}
            </div>

            {showReportForm && (
              <div className="rounded-2xl border border-border bg-surface-alt/70 p-4 sm:p-5">
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Report entry</p>
                  <h4 className="text-sm font-semibold text-text">New daily report</h4>
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Date</label>
                    <input type="date" value={reportForm.report_date} onChange={e => setReportForm(f => ({ ...f, report_date: e.target.value }))} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Hours</label>
                    <input type="number" min={0.5} max={24} step={0.5} value={reportForm.hours} onChange={e => setReportForm(f => ({ ...f, hours: e.target.value }))} placeholder="e.g. 3.5" className={inputClass} />
                  </div>
                </div>
                <div className="mt-4">
                  <label className={fieldLabelClass}>Description</label>
                  <textarea value={reportForm.description} onChange={e => setReportForm(f => ({ ...f, description: e.target.value }))} rows={3} placeholder="What did you work on?" className={textareaClass} />
                </div>
                <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <button type="button" onClick={() => setShowReportForm(false)} className="rounded-xl border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-white">Cancel</button>
                  <button type="button" disabled={addReport.isPending || !reportForm.hours || !reportForm.report_date} onClick={() => addReport.mutate({ report_date: reportForm.report_date, hours: parseFloat(reportForm.hours), description: reportForm.description })} className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50">
                    {addReport.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {reportsQuery.isLoading && <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-text-secondary" /></div>}
            {reportsQuery.data && reportsQuery.data.length === 0 && (
              <div className="rounded-2xl border border-dashed border-gray-200 py-8 text-center">
                <ClipboardList className="mx-auto mb-2 h-7 w-7 text-gray-300" />
                <p className="text-sm font-semibold text-text">No daily reports yet</p>
                <p className="mt-0.5 text-xs text-gray-400">Log execution updates here to build the task history.</p>
              </div>
            )}
            {reportsQuery.data && reportsQuery.data.map(report => (
              <div key={report.id} className={cn('rounded-2xl border px-4 py-3.5 space-y-1.5 shadow-sm', report.is_approved ? 'border-emerald-200 bg-emerald-50' : 'border-border bg-white')}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-text">{report.report_date}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">{report.hours}h</span>
                    {report.is_approved
                      ? <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600"><CheckCircle className="h-3 w-3" /> Approved</span>
                      : <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-600"><Clock className="h-3 w-3" /> Pending</span>
                    }
                  </div>
                  <div className="flex items-center gap-1">
                    {isLead && !report.is_approved && (
                      <button type="button" onClick={() => approveReport.mutate({ reportId: report.id, is_approved: true })} title="Approve" className="rounded p-1 text-emerald-500 hover:bg-emerald-50 transition-colors"><CheckCircle className="h-3.5 w-3.5" /></button>
                    )}
                    {isLead && report.is_approved && (
                      <button type="button" onClick={() => approveReport.mutate({ reportId: report.id, is_approved: false })} title="Revoke approval" className="rounded p-1 text-amber-500 hover:bg-amber-50 transition-colors"><XCircle className="h-3.5 w-3.5" /></button>
                    )}
                    {(isLead || currentUserId === report.reporter_id) && (
                      <button type="button" onClick={() => { if (confirm('Delete this report?')) deleteReport.mutate(report.id) }} title="Delete" className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                    )}
                  </div>
                </div>
                {report.description && <p className="text-xs text-text-secondary">{report.description}</p>}
              </div>
            ))}
          </div>
        ) : (
        <>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {!initial && (
            <div className="mb-3 rounded-xl border border-blue-200 bg-blue-50/60 p-3">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-full bg-blue-100 p-1.5"><AlertTriangle className="h-3.5 w-3.5 text-blue-600" /></div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-blue-900">OPPM task essentials</p>
                  <p className="text-xs leading-5 text-blue-700">Main tasks are top-level deliverables. Sub-tasks belong under a parent task. For full OPPM coverage, set an objective, owner, due date, and contribution.</p>
                </div>
              </div>
            </div>
          )}

          {!initial && mainTaskOptions.length > 0 && (
            <div className="mb-3 flex gap-2">
              <button type="button" onClick={() => setForm(f => ({ ...f, parent_task_id: '' }))} className={cn('flex-1 rounded-xl border-2 px-3 py-2.5 text-center transition-all', !form.parent_task_id ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-white hover:border-gray-300')}>
                <p className={cn('text-sm font-semibold', !form.parent_task_id ? 'text-primary' : 'text-text')}>Main Task</p>
                <p className="mt-0.5 hidden text-[11px] text-text-secondary sm:block">Top-level deliverable</p>
              </button>
              <button type="button" onClick={() => { const firstMain = mainTaskOptions[0]; if (firstMain) setForm(f => ({ ...f, parent_task_id: firstMain.id })) }} className={cn('flex-1 rounded-xl border-2 px-3 py-2.5 text-center transition-all', form.parent_task_id ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-white hover:border-gray-300')}>
                <p className={cn('text-sm font-semibold', form.parent_task_id ? 'text-primary' : 'text-text')}>Sub-Task</p>
                <p className="mt-0.5 hidden text-[11px] text-text-secondary sm:block">Belongs under a main task</p>
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-4">
              <section className={sectionClass}>
                <div className="mb-3 space-y-1">
                  <p className={sectionEyebrowClass}>{briefEyebrow}</p>
                  <h4 className="text-sm font-semibold text-text">{briefTitle}</h4>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr),12rem]">
                  <div>
                    <label className={fieldLabelClass}>Title *</label>
                    <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required placeholder="Task title" className={inputClass} autoFocus />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Due Date *</label>
                    <input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} className={cn(inputClass, dueDateMissing && requiredFieldClass)} required />
                    {dueDateMissing && <p className="mt-1.5 text-xs font-medium text-red-600">Due date is required for OPPM task coverage.</p>}
                  </div>
                </div>
                <div className="mt-3">
                  <label className={fieldLabelClass}>Description</label>
                  <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} placeholder="Add the outcome, key constraints, or handoff notes" className={textareaClass} />
                </div>
              </section>

              <section className={sectionClass}>
                <div className="mb-3 space-y-1">
                  <p className={sectionEyebrowClass}>Delivery setup</p>
                  <h4 className="text-sm font-semibold text-text">{deliveryTitle}</h4>
                </div>
                <div className={cn('grid grid-cols-1 gap-3 md:grid-cols-2', initial ? 'xl:grid-cols-5' : 'xl:grid-cols-4')}>
                  <div>
                    <label className={fieldLabelClass}>Priority</label>
                    <select value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as Priority }))} className={selectClass}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  {initial && (
                    <div>
                      <label className={fieldLabelClass}>Status</label>
                      <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as TaskStatus }))} className={selectClass}>
                        <option value="todo">To Do</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                      </select>
                    </div>
                  )}
                  <div>
                    <label className={fieldLabelClass}>Progress (%)</label>
                    <input type="number" min={0} max={100} value={form.progress} onChange={(e) => setForm((f) => ({ ...f, progress: parseInt(e.target.value) || 0 }))} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Contribution (%)</label>
                    <input type="number" min={0} max={100} value={form.project_contribution} onChange={(e) => setForm((f) => ({ ...f, project_contribution: parseInt(e.target.value) || 0 }))} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Start Date</label>
                    <input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} className={inputClass} />
                  </div>
                </div>
                <p className="mt-2 text-xs text-text-secondary">Contribution weights how much this task affects project progress in the OPPM roll-up.</p>
              </section>
            </div>

            <div className="space-y-4">
              <section className={sectionClass}>
                <div className="mb-3 space-y-1">
                  <p className={sectionEyebrowClass}>Ownership and alignment</p>
                  <h4 className="text-sm font-semibold text-text">Connect the task to the delivery plan</h4>
                  <p className="text-xs text-text-secondary">Link to an objective, assign an owner, and choose a parent task when you need a sub-task.</p>
                </div>

                <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Linked Objective *</label>
                    {availableObjectives.length > 0 ? (
                      <>
                        <select value={form.oppm_objective_id} onChange={(e) => setForm((f) => ({ ...f, oppm_objective_id: e.target.value }))} className={cn(selectClass, objectiveMissing && requiredFieldClass)} required>
                          <option value="">None (not linked to OPPM)</option>
                          {availableObjectives.map((obj, i) => (
                            <option key={obj.id} value={obj.id}>{String.fromCharCode(65 + i)}. {obj.title}</option>
                          ))}
                        </select>
                        <p className="mt-1.5 text-xs text-text-secondary">{selectedObjective ? `Currently linked to ${selectedObjective.title}.` : 'Linking an objective keeps the task visible in the OPPM layer.'}</p>
                        {objectiveMissing && <p className="mt-1.5 text-xs font-medium text-red-600">Choose an objective before saving this task.</p>}
                        <div className="mt-2">
                          <button type="button" onClick={() => { setShowObjectiveCreator(v => !v); setObjectiveNotice(null) }} className="text-xs font-semibold text-primary transition-colors hover:text-primary-dark">
                            {showObjectiveCreator ? 'Cancel new objective' : 'Add another objective'}
                          </button>
                        </div>
                        {showObjectiveCreator && (
                          <div className="mt-2 rounded-xl border border-dashed border-gray-200 px-3.5 py-3 text-sm text-text-secondary">
                            <p className="font-medium text-text">Create another objective</p>
                            <p className="mt-1 text-xs text-text-secondary">Add the objective you want, then it will be linked to this task automatically.</p>
                            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                              <input value={manualObjectiveTitle} onChange={(e) => { setManualObjectiveTitle(e.target.value); if (objectiveNotice) setObjectiveNotice(null) }} placeholder="e.g. Launch production environment" className={inputClass} />
                              <button type="button" onClick={() => createObjective.mutate(manualObjectiveTitle.trim())} disabled={createObjective.isPending || !manualObjectiveTitle.trim() || !projectId} className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50">
                                {createObjective.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create objective'}
                              </button>
                            </div>
                            {objectiveNotice && <p className={cn('mt-2 text-xs', createObjective.isError ? 'text-red-600' : 'text-emerald-600')}>{objectiveNotice}</p>}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className={cn('rounded-xl border border-dashed border-gray-200 px-3.5 py-3 text-sm text-text-secondary', objectiveMissing && 'border-red-300 bg-red-50/40')}>
                        <p className="font-medium text-text">No objectives yet.</p>
                        <p className="mt-1 text-xs text-text-secondary">Create one here to link this task without relying on AI draft generation.</p>
                        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                          <input value={manualObjectiveTitle} onChange={(e) => { setManualObjectiveTitle(e.target.value); if (objectiveNotice) setObjectiveNotice(null) }} placeholder="e.g. Launch production environment" className={inputClass} />
                          <button type="button" onClick={() => createObjective.mutate(manualObjectiveTitle.trim())} disabled={createObjective.isPending || !manualObjectiveTitle.trim() || !projectId} className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50">
                            {createObjective.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create objective'}
                          </button>
                        </div>
                        {objectiveMissing && <p className="mt-2 text-xs font-medium text-red-600">Create and link an objective before saving this task.</p>}
                        {objectiveNotice && <p className={cn('mt-2 text-xs', createObjective.isError ? 'text-red-600' : 'text-emerald-600')}>{objectiveNotice}</p>}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className={fieldLabelClass}>Owner *</label>
                    {members.length > 0 ? (
                      <>
                        <select
                          value={form.assignee_id}
                          onChange={(e) => {
                            const userId = e.target.value
                            setForm((f) => ({ ...f, assignee_id: userId }))
                            const workspaceMember = workspaceMemberByUserId.get(userId)
                            const projectAllMember = workspaceMember
                              ? projectAllMemberByWorkspaceMemberId.get(workspaceMember.id)
                              : undefined
                            const hasPrimaryOwner = ownerAssignments.some((assignment) => assignment.priority === 'A')
                            if (!workspaceMember || !projectAllMember || !hasPrimaryOwner) {
                              return
                            }
                            handleOwnerAssignmentsChange([
                              ...ownerAssignments.filter((assignment) => assignment.priority !== 'A' && assignment.member_id !== projectAllMember.id),
                              { member_id: projectAllMember.id, priority: 'A' },
                            ])
                          }}
                          className={cn(selectClass, ownerMissing && requiredFieldClass)}
                          required
                        >
                          <option value="">Unassigned</option>
                          {members.map((m) => (
                            <option key={m.id} value={m.user_id}>
                              {m.display_name || m.email || m.user_id.slice(0, 8)}
                              {m.role === 'owner' ? ' (Owner)' : m.role === 'admin' ? ' (Admin)' : ''}
                            </option>
                          ))}
                        </select>
                        <p className="mt-1.5 text-xs text-text-secondary">{selectedOwner ? `Primary owner: ${selectedOwner.display_name || selectedOwner.email || 'Assigned member'}.` : 'Assign an owner to keep accountability clear.'}</p>
                        {ownerMissing && <p className="mt-1.5 text-xs font-medium text-red-600">Assign an owner before saving this task.</p>}

                        <div className="mt-2.5">
                          <button type="button" onClick={() => setShowAdvancedOwners((value) => !value)} className={disclosureButtonClass}>
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-text">Advanced A/B/C owners</p>
                              <p className="text-xs text-text-secondary">{ownerAssignments.length > 0 ? `${ownerAssignments.length} OPPM owner role${ownerAssignments.length === 1 ? '' : 's'} set.` : 'Add accountable and helper owners only when you need the OPPM owner grid.'}</p>
                            </div>
                            {showAdvancedOwners ? <ChevronUp className="h-4 w-4 shrink-0 text-text-secondary" /> : <ChevronDown className="h-4 w-4 shrink-0 text-text-secondary" />}
                          </button>
                          {showAdvancedOwners && (
                            <div className="mt-2.5 space-y-1.5">
                              <TaskOwnerEditor
                                members={allMembers}
                                assignments={ownerAssignments}
                                onChange={handleOwnerAssignmentsChange}
                              />
                              <p className="text-xs text-text-secondary">
                                {initial
                                  ? 'A/B/C ownership is saved with this task update and refreshes the OPPM owner grid.'
                                  : 'A/B/C ownership will be saved right after the task is created.'}
                              </p>
                            </div>
                          )}
                        </div>
                      </>
                    ) : (
                      <p className="rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm italic text-text-secondary">No workspace members found.</p>
                    )}
                  </div>
                </div>

                <div className="mt-3">
                  <label className={fieldLabelClass}>Parent Task (makes this a sub-task)</label>
                  {mainTaskOptions.length > 0 ? (
                    <>
                      <select value={form.parent_task_id} onChange={(e) => setForm((f) => ({ ...f, parent_task_id: e.target.value }))} className={cn(selectClass, form.parent_task_id && 'border-primary ring-2 ring-primary/10')}>
                        <option value="">None (this is a main task)</option>
                        {mainTaskOptions.map((t) => (
                          <option key={t.id} value={t.id}>↳ {t.title}</option>
                        ))}
                      </select>
                      {form.parent_task_id ? (
                        <div className="mt-1.5 flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                          <GitBranch className="h-3.5 w-3.5 text-primary shrink-0" />
                          <p className="text-xs text-primary font-medium">Sub-task of "{allTasks.find(t => t.id === form.parent_task_id)?.title}"</p>
                        </div>
                      ) : (
                        <p className="mt-1.5 text-xs text-text-secondary">Leave empty to create a top-level main task. Select a parent to nest this as a sub-task.</p>
                      )}
                    </>
                  ) : (
                    <div className="rounded-xl border border-dashed border-gray-200 px-4 py-3">
                      <p className="text-sm italic text-text-secondary">No main tasks yet — this will be created as a <strong>main task</strong>.</p>
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
            {virtualMemberOptions.length > 0 && (
              <section className={sectionClass}>
                <button type="button" onClick={() => setShowVirtualAssignees((value) => !value)} className={disclosureButtonClass}>
                  <div className="min-w-0">
                    <p className={sectionEyebrowClass}>External Assignees</p>
                    <p className="mt-0.5 text-sm font-semibold text-text">Optional external support</p>
                    <p className="text-xs text-text-secondary">{virtualAssignees.length > 0 ? `${virtualAssignees.length} external assignee${virtualAssignees.length === 1 ? '' : 's'} selected.` : 'Only expand this when virtual members need to support the task.'}</p>
                  </div>
                  {showVirtualAssignees ? <ChevronUp className="h-4 w-4 shrink-0 text-text-secondary" /> : <ChevronDown className="h-4 w-4 shrink-0 text-text-secondary" />}
                </button>
                {showVirtualAssignees && (
                  <div className="mt-2.5 max-h-36 overflow-y-auto space-y-1.5 rounded-xl border border-border bg-white p-2">
                    {virtualMemberOptions.map((member) => (
                      <label key={member.id} className={cn('flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-sm transition-colors', virtualAssignees.includes(member.member_id) ? 'border-primary/40 bg-primary/5 text-primary' : 'border-border bg-white text-text hover:bg-surface-alt')}>
                        <input type="checkbox" checked={virtualAssignees.includes(member.member_id)} onChange={() => toggleVirtualAssignee(member.member_id)} className="h-3.5 w-3.5 accent-primary shrink-0" />
                        <span className="flex-1 min-w-0 font-medium">{member.name}</span>
                        <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">External</span>
                      </label>
                    ))}
                  </div>
                )}
              </section>
            )}

            {allTasks.length > 0 && (
              <section className={sectionClass}>
                <button type="button" onClick={() => setShowDependencies((value) => !value)} className={disclosureButtonClass}>
                  <div className="min-w-0">
                    <p className={sectionEyebrowClass}>Dependencies</p>
                    <p className="mt-0.5 text-sm font-semibold text-text">This task depends on</p>
                    <p className="text-xs text-text-secondary">{dependsOn.length > 0 ? `${dependsOn.length} dependenc${dependsOn.length === 1 ? 'y' : 'ies'} selected.` : 'Optional blocking tasks that must finish first.'}</p>
                  </div>
                  {showDependencies ? <ChevronUp className="h-4 w-4 shrink-0 text-text-secondary" /> : <ChevronDown className="h-4 w-4 shrink-0 text-text-secondary" />}
                </button>
                {showDependencies && (
                  <div className="mt-2.5 max-h-44 overflow-y-auto space-y-1.5">
                    {allTasks.map((t) => (
                      <label key={t.id} className={cn('flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors', dependsOn.includes(t.id) ? 'border-primary/40 bg-primary/5 text-primary' : 'border-border bg-white text-text hover:bg-surface-alt')}>
                        <input type="checkbox" checked={dependsOn.includes(t.id)} onChange={() => toggleDependency(t.id)} className="h-3.5 w-3.5 accent-primary shrink-0" />
                        <span className="flex-1 min-w-0 font-medium">{t.title}</span>
                        <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium', STATUS_BADGE[t.status])}>{STATUS_LABEL[t.status]}</span>
                      </label>
                    ))}
                  </div>
                )}
              </section>
            )}

            {subObjectives.length > 0 && (
              <section className={cn(sectionClass, virtualMemberOptions.length > 0 && allTasks.length > 0 && 'xl:col-span-2')}>
                <button type="button" onClick={() => setShowSubObjectives((value) => !value)} className={disclosureButtonClass}>
                  <div className="min-w-0">
                    <p className={sectionEyebrowClass}>Sub Objectives</p>
                    <p className="mt-0.5 text-sm font-semibold text-text">Which sub-objectives does this task contribute to?</p>
                    <p className="text-xs text-text-secondary">{subObjIds.length > 0 ? `${subObjIds.length} sub-objective${subObjIds.length === 1 ? '' : 's'} linked.` : 'Optional OPPM sub-objectives this task helps advance.'}</p>
                  </div>
                  {showSubObjectives ? <ChevronUp className="h-4 w-4 shrink-0 text-text-secondary" /> : <ChevronDown className="h-4 w-4 shrink-0 text-text-secondary" />}
                </button>
                {showSubObjectives && (
                  <div className="mt-2.5 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                    {Array.from({ length: 6 }, (_, i) => {
                      const so = subObjectives.find(s => s.position === i + 1)
                      if (!so) return null
                      const checked = subObjIds.includes(so.id)
                      return (
                        <label key={so.id} className={cn('flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2 text-xs transition-colors', checked ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-border bg-white text-text hover:bg-surface-alt')}>
                          <input type="checkbox" checked={checked} onChange={() => toggleSubObj(so.id)} className="mt-0.5 h-3.5 w-3.5 accent-indigo-600 shrink-0" />
                          <span className="mt-px shrink-0 text-[10px] font-bold">{i + 1}.</span>
                          <span className="font-medium leading-tight">{so.label}</span>
                        </label>
                      )
                    }).filter(Boolean)}
                  </div>
                )}
              </section>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-border bg-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-3">
          <div className="min-w-0">
            <p className={cn('text-sm font-semibold', isOppmAligned ? 'text-emerald-700' : submitAttempted ? 'text-red-700' : 'text-text')}>{footerTitle}</p>
            <p className="text-xs text-text-secondary">{footerMessage}</p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button type="button" onClick={onCancel} className="rounded-xl border border-border px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-alt sm:px-4 sm:py-2.5">Cancel</button>
            <button type="submit" disabled={isPending || !form.title.trim()} className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50 sm:px-5 sm:py-2.5">
              {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : initial ? 'Save Changes' : 'Create Task'}
            </button>
          </div>
        </div>
        </>
        )}
      </form>
    </div>
  )
}
