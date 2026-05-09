import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Task, TaskReport, OPPMObjective, OPPMSubObjective, WorkspaceMember, Priority, TaskStatus } from '@/types'
import { cn } from '@/lib/utils'
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
  const [tab, setTab] = useState<'details' | 'reports'>('details')
  const [reportForm, setReportForm] = useState({ report_date: new Date().toISOString().slice(0, 10), hours: '', description: '' })
  const [showReportForm, setShowReportForm] = useState(false)
  const [manualObjectiveTitle, setManualObjectiveTitle] = useState('')
  const [createdObjectives, setCreatedObjectives] = useState<OPPMObjective[]>([])
  const [objectiveNotice, setObjectiveNotice] = useState<string | null>(null)
  const [showObjectiveCreator, setShowObjectiveCreator] = useState(false)

  const reportsQuery = useQuery<TaskReport[]>({
    queryKey: ['task-reports', initial?.id],
    queryFn: () => api.get<TaskReport[]>(`${wsPath}/tasks/${initial!.id}/reports`),
    enabled: !!initial && tab === 'reports',
  })

  const addReport = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post(`${wsPath}/tasks/${initial!.id}/reports`, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['task-reports', initial?.id] }); setReportForm({ report_date: new Date().toISOString().slice(0, 10), hours: '', description: '' }); setShowReportForm(false) },
  })

  const approveReport = useMutation({
    mutationFn: ({ reportId, is_approved }: { reportId: string; is_approved: boolean }) =>
      api.patch<TaskReport>(`${wsPath}/tasks/${initial!.id}/reports/${reportId}/approve`, { is_approved }),
    onSuccess: (updated) => {
      queryClient.setQueryData<TaskReport[]>(
        ['task-reports', initial?.id],
        (old) => old ? old.map((r) => r.id === updated.id ? updated : r) : old,
      )
    },
  })

  const deleteReport = useMutation({
    mutationFn: (reportId: string) => api.delete(`${wsPath}/tasks/${initial!.id}/reports/${reportId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task-reports', initial?.id] }),
  })

  const createObjective = useMutation({
    mutationFn: (objectiveTitle: string) =>
      api.post<OPPMObjective>(`${wsPath}/projects/${projectId}/oppm/objectives`, { title: objectiveTitle }),
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
    start_date: initial?.start_date || '',
    due_date: initial?.due_date || '',
    oppm_objective_id: initial?.oppm_objective_id || '',
    assignee_id: initial?.assignee_id || '',
    parent_task_id: initial?.parent_task_id || '',
  })
  const [dependsOn, setDependsOn] = useState<string[]>(initial?.depends_on ?? [])
  const [subObjIds, setSubObjIds] = useState<string[]>((initial as unknown as Record<string, unknown>)?.sub_objective_ids as string[] ?? [])
  const [virtualAssignees, setVirtualAssignees] = useState<string[]>(initial?.virtual_assignees?.map((v) => v.virtual_member_id) ?? [])

  const toggleDependency = (taskId: string) => {
    setDependsOn((prev) => prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId])
  }

  const toggleSubObj = (soId: string) => {
    setSubObjIds((prev) => prev.includes(soId) ? prev.filter((id) => id !== soId) : [...prev, soId])
  }

  const toggleVirtualAssignee = (vmId: string) => {
    setVirtualAssignees((prev) => prev.includes(vmId) ? prev.filter((id) => id !== vmId) : [...prev, vmId])
  }

  const availableObjectives = [
    ...objectives,
    ...createdObjectives.filter((created) => !objectives.some((objective) => objective.id === created.id)),
  ]

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title.trim()) return
    const data: Record<string, unknown> = { ...form, depends_on: dependsOn, sub_objective_ids: subObjIds, virtual_assignees: virtualAssignees }
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

  const missingPillars: string[] = []
  if (!form.oppm_objective_id) missingPillars.push('Objective')
  if (!form.assignee_id) missingPillars.push('Owner')
  if (!form.due_date) missingPillars.push('Due date')

  const isOppmAligned = missingPillars.length === 0
  const selectedObjective = availableObjectives.find((objective) => objective.id === form.oppm_objective_id)
  const selectedOwner = members.find((member) => member.user_id === form.assignee_id)

  const fieldLabelClass = 'mb-2 block text-[11px] font-semibold uppercase tracking-[0.08em] text-text-secondary'
  const inputClass = 'w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-4 focus:ring-primary/10'
  const selectClass = 'w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-4 focus:ring-primary/10'
  const textareaClass = 'w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-4 focus:ring-primary/10 resize-none'
  const sectionClass = 'rounded-2xl border border-border bg-surface-alt/70 p-4 sm:p-5'
  const sectionEyebrowClass = 'text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onCancel}>
      <form
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-[min(100%-1rem,72rem)] flex-col overflow-hidden rounded-[1.75rem] border border-border bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary">
                {initial ? 'Update execution details' : 'Add execution details'}
              </p>
              <h3 className="text-lg font-semibold text-text">{title}</h3>
              <p className="text-sm text-text-secondary">Keep the task brief clear, link it to the right objective, and set ownership without crowding the form.</p>
            </div>
            <button type="button" onClick={onCancel} className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
              <X className="h-4.5 w-4.5" />
            </button>
          </div>
          {initial && (
            <div className="flex gap-1.5 overflow-x-auto pb-3">
              <button type="button" onClick={() => setTab('details')} className={cn('flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold transition-colors', tab === 'details' ? 'bg-primary/10 text-primary ring-1 ring-primary/15' : 'bg-surface-alt text-text-secondary hover:text-text')}>
                <Pencil className="h-3.5 w-3.5" /> Details
              </button>
              <button type="button" onClick={() => setTab('reports')} className={cn('flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold transition-colors', tab === 'reports' ? 'bg-primary/10 text-primary ring-1 ring-primary/15' : 'bg-surface-alt text-text-secondary hover:text-text')}>
                <ClipboardList className="h-3.5 w-3.5" /> Daily Reports
                {reportsQuery.data && reportsQuery.data.length > 0 && (
                  <span className="ml-1 rounded-full bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-600 ring-1 ring-slate-200">{reportsQuery.data.length}</span>
                )}
              </button>
            </div>
          )}
        </div>

        {tab === 'reports' && initial ? (
          <div className="max-h-[72vh] space-y-4 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-text-secondary">
                Total hours logged: <span className="font-semibold text-text">{reportsQuery.data ? reportsQuery.data.reduce((s, r) => s + r.hours, 0).toFixed(1) : '—'}</span>
              </p>
              {(!initial?.assignee_id || initial.assignee_id === currentUserId) && (
                <button type="button" onClick={() => setShowReportForm(v => !v)} className="inline-flex items-center justify-center gap-1 rounded-xl bg-primary px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark">
                  <Plus className="h-3.5 w-3.5" /> Add Report
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
              <div className="rounded-2xl border border-dashed border-gray-200 py-10 text-center">
                <ClipboardList className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                <p className="text-sm text-text-secondary">No reports yet</p>
                <p className="text-xs text-gray-400 mt-0.5">Submit a daily report to track your work</p>
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
        <div className="max-h-[72vh] overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {!initial && (
            <div className="mb-5 rounded-2xl border border-blue-200 bg-blue-50/60 p-4">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-full bg-blue-100 p-1.5"><AlertTriangle className="h-3.5 w-3.5 text-blue-600" /></div>
                <div className="space-y-1.5">
                  <p className="text-sm font-semibold text-blue-900">How OPPM task hierarchy works</p>
                  <div className="text-xs text-blue-700 space-y-1">
                    <p><strong>Step 1:</strong> Create <strong>Main Tasks</strong> — these are the major deliverables.</p>
                    <p><strong>Step 2:</strong> Create <strong>Sub-Tasks</strong> under each main task by selecting a <strong>Parent Task</strong> below.</p>
                    <p><strong>Tip:</strong> Link every task to an <strong>Objective</strong> and assign an <strong>Owner</strong> for full OPPM alignment.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {!initial && allTasks.filter(t => !t.parent_task_id).length > 0 && (
            <div className="mb-5 flex gap-2">
              <button type="button" onClick={() => setForm(f => ({ ...f, parent_task_id: '' }))} className={cn('flex-1 rounded-xl border-2 px-4 py-3 text-center transition-all', !form.parent_task_id ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-white hover:border-gray-300')}>
                <p className={cn('text-sm font-semibold', !form.parent_task_id ? 'text-primary' : 'text-text')}>Main Task</p>
                <p className="text-[11px] text-text-secondary mt-0.5">Top-level deliverable</p>
              </button>
              <button type="button" onClick={() => { const firstMain = allTasks.find(t => !t.parent_task_id); if (firstMain) setForm(f => ({ ...f, parent_task_id: firstMain.id })) }} className={cn('flex-1 rounded-xl border-2 px-4 py-3 text-center transition-all', form.parent_task_id ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-white hover:border-gray-300')}>
                <p className={cn('text-sm font-semibold', form.parent_task_id ? 'text-primary' : 'text-text')}>Sub-Task</p>
                <p className="text-[11px] text-text-secondary mt-0.5">Belongs under a main task</p>
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="space-y-5">
              <section className={sectionClass}>
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Task brief</p>
                  <h4 className="text-sm font-semibold text-text">What needs to get done?</h4>
                </div>
                <div>
                  <label className={fieldLabelClass}>Title *</label>
                  <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required placeholder="Task title" className={inputClass} autoFocus />
                </div>
                <div className="mt-4">
                  <label className={fieldLabelClass}>Description</label>
                  <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={4} placeholder="Add the outcome, key constraints, or handoff notes" className={textareaClass} />
                </div>
              </section>

              <section className={sectionClass}>
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Delivery setup</p>
                  <h4 className="text-sm font-semibold text-text">Schedule, progress, and workflow state</h4>
                </div>
                <div className={cn('grid grid-cols-1 gap-4 md:grid-cols-2', initial && 'xl:grid-cols-3')}>
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
                </div>
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Start Date</label>
                    <input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} className={inputClass} />
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Due Date</label>
                    <input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} className={inputClass} />
                  </div>
                </div>
              </section>
            </div>

            <div className="space-y-5">
              <section className={sectionClass}>
                <div className="mb-4 space-y-1">
                  <p className={sectionEyebrowClass}>Ownership and alignment</p>
                  <h4 className="text-sm font-semibold text-text">Connect the task to the delivery plan</h4>
                  <p className="text-xs text-text-secondary">Link to an objective and assign an owner for OPPM visibility. Set a parent task to create a sub-task.</p>
                </div>

                <div>
                  <label className={fieldLabelClass}>Linked Objective</label>
                  {availableObjectives.length > 0 ? (
                    <>
                      <select value={form.oppm_objective_id} onChange={(e) => setForm((f) => ({ ...f, oppm_objective_id: e.target.value }))} className={selectClass}>
                        <option value="">None (not linked to OPPM)</option>
                        {availableObjectives.map((obj, i) => (
                          <option key={obj.id} value={obj.id}>{String.fromCharCode(65 + i)}. {obj.title}</option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs text-text-secondary">{selectedObjective ? `Currently linked to ${selectedObjective.title}.` : 'Linking an objective keeps the task visible in the OPPM layer.'}</p>
                      <div className="mt-3">
                        <button type="button" onClick={() => { setShowObjectiveCreator(v => !v); setObjectiveNotice(null) }} className="text-xs font-semibold text-primary transition-colors hover:text-primary-dark">
                          {showObjectiveCreator ? 'Cancel new objective' : 'Add another objective'}
                        </button>
                      </div>
                      {showObjectiveCreator && (
                        <div className="mt-3 rounded-xl border border-dashed border-gray-200 px-4 py-4 text-sm text-text-secondary">
                          <p className="font-medium text-text">Create another objective</p>
                          <p className="mt-1 text-xs text-text-secondary">Add the objective you want, then it will be linked to this task automatically.</p>
                          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                            <input value={manualObjectiveTitle} onChange={(e) => { setManualObjectiveTitle(e.target.value); if (objectiveNotice) setObjectiveNotice(null) }} placeholder="e.g. Launch production environment" className={inputClass} />
                            <button type="button" onClick={() => createObjective.mutate(manualObjectiveTitle.trim())} disabled={createObjective.isPending || !manualObjectiveTitle.trim() || !projectId} className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50">
                              {createObjective.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create objective'}
                            </button>
                          </div>
                          {objectiveNotice && <p className={cn('mt-2 text-xs', createObjective.isError ? 'text-red-600' : 'text-emerald-600')}>{objectiveNotice}</p>}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="rounded-xl border border-dashed border-gray-200 px-4 py-4 text-sm text-text-secondary">
                      <p className="font-medium text-text">No objectives yet.</p>
                      <p className="mt-1 text-xs text-text-secondary">Create one here to link this task without relying on AI draft generation.</p>
                      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                        <input value={manualObjectiveTitle} onChange={(e) => { setManualObjectiveTitle(e.target.value); if (objectiveNotice) setObjectiveNotice(null) }} placeholder="e.g. Launch production environment" className={inputClass} />
                        <button type="button" onClick={() => createObjective.mutate(manualObjectiveTitle.trim())} disabled={createObjective.isPending || !manualObjectiveTitle.trim() || !projectId} className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50">
                          {createObjective.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create objective'}
                        </button>
                      </div>
                      {objectiveNotice && <p className={cn('mt-2 text-xs', createObjective.isError ? 'text-red-600' : 'text-emerald-600')}>{objectiveNotice}</p>}
                    </div>
                  )}
                </div>

                <div className="mt-4">
                  <label className={fieldLabelClass}>Parent Task (makes this a sub-task)</label>
                  {allTasks.filter(t => !t.parent_task_id && t.id !== initial?.id).length > 0 ? (
                    <>
                      <select value={form.parent_task_id} onChange={(e) => setForm((f) => ({ ...f, parent_task_id: e.target.value }))} className={cn(selectClass, form.parent_task_id && 'border-primary ring-2 ring-primary/10')}>
                        <option value="">None (this is a main task)</option>
                        {allTasks.filter(t => !t.parent_task_id && t.id !== initial?.id).map((t) => (
                          <option key={t.id} value={t.id}>↳ {t.title}</option>
                        ))}
                      </select>
                      {form.parent_task_id ? (
                        <div className="mt-2 flex items-center gap-2 rounded-lg bg-primary/5 border border-primary/20 px-3 py-2">
                          <GitBranch className="h-3.5 w-3.5 text-primary shrink-0" />
                          <p className="text-xs text-primary font-medium">Sub-task of "{allTasks.find(t => t.id === form.parent_task_id)?.title}"</p>
                        </div>
                      ) : (
                        <p className="mt-2 text-xs text-text-secondary">Leave empty to create a top-level main task. Select a parent to nest this as a sub-task.</p>
                      )}
                    </>
                  ) : (
                    <div className="rounded-xl border border-dashed border-gray-200 px-4 py-3">
                      <p className="text-sm italic text-text-secondary">No main tasks yet — this will be created as a <strong>main task</strong>.</p>
                    </div>
                  )}
                </div>

                <div className="mt-4">
                  <label className={fieldLabelClass}>Owner</label>
                  {members.length > 0 ? (
                    <>
                      <select value={form.assignee_id} onChange={(e) => setForm((f) => ({ ...f, assignee_id: e.target.value }))} className={selectClass}>
                        <option value="">Unassigned</option>
                        {members.map((m) => (
                          <option key={m.id} value={m.user_id}>
                            {m.display_name || m.email || m.user_id.slice(0, 8)}
                            {m.role === 'owner' ? ' (Owner)' : m.role === 'admin' ? ' (Admin)' : ''}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs text-text-secondary">{selectedOwner ? `Primary owner: ${selectedOwner.display_name || selectedOwner.email || 'Assigned member'}.` : 'Assign an owner to keep accountability clear.'}</p>
                    </>
                  ) : (
                    <p className="rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm italic text-text-secondary">No workspace members found.</p>
                  )}
                </div>

                {allMembers.filter((m) => m.source === 'virtual').length > 0 && (
                  <div className="mt-4">
                    <label className={fieldLabelClass}>External Assignees</label>
                    <div className="max-h-40 overflow-y-auto space-y-1.5 rounded-xl border border-border bg-white p-2">
                      {allMembers.filter((m) => m.source === 'virtual').map((m) => (
                        <label key={m.id} className={cn('flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-sm transition-colors', virtualAssignees.includes(m.member_id) ? 'border-primary/40 bg-primary/5 text-primary' : 'border-border bg-white text-text hover:bg-surface-alt')}>
                          <input type="checkbox" checked={virtualAssignees.includes(m.member_id)} onChange={() => toggleVirtualAssignee(m.member_id)} className="h-3.5 w-3.5 accent-primary shrink-0" />
                          <span className="flex-1 min-w-0 font-medium">{m.name}</span>
                          <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">External</span>
                        </label>
                      ))}
                    </div>
                    {virtualAssignees.length > 0 && (
                      <p className="mt-2 text-xs text-primary font-medium">{virtualAssignees.length} external assignee{virtualAssignees.length === 1 ? '' : 's'} selected</p>
                    )}
                  </div>
                )}
              </section>

              {allTasks.length > 0 && (
                <section className={sectionClass}>
                  <div className="mb-3 space-y-1">
                    <p className={sectionEyebrowClass}>Dependencies</p>
                    <h4 className="text-sm font-semibold text-text">This task depends on</h4>
                    <p className="text-xs text-text-secondary">Select tasks that must be completed before this one can start.</p>
                  </div>
                  <div className="max-h-52 overflow-y-auto space-y-1.5">
                    {allTasks.map((t) => (
                      <label key={t.id} className={cn('flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors', dependsOn.includes(t.id) ? 'border-primary/40 bg-primary/5 text-primary' : 'border-border bg-white text-text hover:bg-surface-alt')}>
                        <input type="checkbox" checked={dependsOn.includes(t.id)} onChange={() => toggleDependency(t.id)} className="h-3.5 w-3.5 accent-primary shrink-0" />
                        <span className="flex-1 min-w-0 font-medium">{t.title}</span>
                        <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium', STATUS_BADGE[t.status])}>{STATUS_LABEL[t.status]}</span>
                      </label>
                    ))}
                  </div>
                  {dependsOn.length > 0 && (
                    <p className="mt-2 text-xs text-primary font-medium">{dependsOn.length} dependenc{dependsOn.length === 1 ? 'y' : 'ies'} set</p>
                  )}
                </section>
              )}

              {subObjectives.length > 0 && (
                <section className={sectionClass}>
                  <div className="mb-3 space-y-1">
                    <p className={sectionEyebrowClass}>Sub Objectives</p>
                    <h4 className="text-sm font-semibold text-text">Which sub-objectives does this task contribute to?</h4>
                    <p className="text-xs text-text-secondary">Select the OPPM sub-objectives this task helps achieve.</p>
                  </div>
                  <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                    {Array.from({ length: 6 }, (_, i) => {
                      const so = subObjectives.find(s => s.position === i + 1)
                      if (!so) return null
                      const checked = subObjIds.includes(so.id)
                      return (
                        <label key={so.id} className={cn('flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2 text-xs transition-colors', checked ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-border bg-white text-text hover:bg-surface-alt')}>
                          <input type="checkbox" checked={checked} onChange={() => toggleSubObj(so.id)} className="mt-0.5 h-3.5 w-3.5 accent-indigo-600 shrink-0" />
                          <span className="font-bold text-[10px] shrink-0 mt-px">{i + 1}.</span>
                          <span className="font-medium leading-tight">{so.label}</span>
                        </label>
                      )
                    }).filter(Boolean)}
                  </div>
                  {subObjIds.length > 0 && (
                    <p className="mt-2 text-xs text-indigo-600 font-medium">{subObjIds.length} sub-objective{subObjIds.length > 1 ? 's' : ''} linked</p>
                  )}
                </section>
              )}

              <section className={cn(sectionClass, isOppmAligned ? 'border-emerald-200 bg-emerald-50/80' : 'border-amber-200 bg-amber-50/80')}>
                <div className="flex items-start gap-3">
                  <div className={cn('mt-0.5 rounded-full p-2', isOppmAligned ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>
                    {isOppmAligned ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-text">{isOppmAligned ? 'OPPM aligned' : `${missingPillars.length} OPPM field${missingPillars.length > 1 ? 's' : ''} missing`}</p>
                    <p className="text-sm text-text-secondary">{isOppmAligned ? 'Objective, owner, and due date are all set. This task will sit cleanly in the delivery plan.' : `Still missing: ${missingPillars.join(', ')}.`}</p>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-border bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className={cn('text-sm font-semibold', isOppmAligned ? 'text-emerald-700' : 'text-amber-700')}>{isOppmAligned ? 'Ready to save' : 'Needs a little more alignment'}</p>
            <p className="text-xs text-text-secondary">{isOppmAligned ? 'This task has the core OPPM fields in place.' : `Add ${missingPillars.join(', ')} when you want full OPPM coverage.`}</p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button type="button" onClick={onCancel} className="rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-alt">Cancel</button>
            <button type="submit" disabled={isPending || !form.title.trim()} className="inline-flex items-center justify-center rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50">
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
