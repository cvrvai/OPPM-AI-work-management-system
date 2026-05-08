import { useState } from 'react'
import { cn, getStatusColor } from '@/lib/utils'
import type { Project, Priority, WorkspaceMember } from '@/types'
import { X, DollarSign, Clock } from 'lucide-react'
import {
  fieldLabelClass,
  inputClass,
  selectClass,
  textareaClass,
  sectionEyebrowClass,
  modalShellClass,
  secondaryButtonClass,
  primaryButtonClass,
  getMemberLabel,
} from './constants'

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

export function EditProjectModal({
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
      <form onSubmit={handleSubmit} className={modalShellClass} onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className={sectionEyebrowClass}>Update planning details</p>
              <h2 className="text-lg font-semibold text-text">Edit Project</h2>
              <p className="text-sm text-text-secondary">Refine the schedule, planning inputs, and leadership details without leaving the projects list.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"><X className="h-4.5 w-4.5" /></button>
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
                  <div><label className={fieldLabelClass}>Start Date</label><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputClass} /></div>
                  <div><label className={fieldLabelClass}>Deadline</label><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={inputClass} /></div>
                  <div><label className={fieldLabelClass}>End Date</label><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={inputClass} /></div>
                </div>
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-text">Resources & ownership</h3>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div>
                    <label className={fieldLabelClass}>Budget</label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                      <input type="number" min="0" step="0.01" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 50,000" className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10" />
                    </div>
                  </div>
                  <div>
                    <label className={fieldLabelClass}>Planning Hours</label>
                    <div className="relative">
                      <Clock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                      <input type="number" min="0" step="0.5" value={planningHours} onChange={(e) => setPlanningHours(e.target.value)} placeholder="e.g. 120" className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3.5 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10" />
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
                        <option key={member.id} value={member.id}>{getMemberLabel(member)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>
            </div>

            <div className="mt-6 space-y-5 xl:col-span-2 xl:mt-0">
              <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">Preview</p>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">{title.trim() || 'Untitled project'}</p>
                    <p className="mt-1 text-xs text-text-secondary line-clamp-2">{objectiveSummary.trim() || 'No objective summary yet.'}</p>
                  </div>
                  <span className={cn('shrink-0 rounded-md px-2 py-0.5 text-xs font-medium', getStatusColor(status))}>{status.replace('_', ' ')}</span>
                </div>
                <div className="mt-4 divide-y divide-border text-sm">
                  <div className="flex items-center justify-between gap-3 py-2">
                    <span className="text-text-secondary">Leader</span>
                    <span className="font-medium text-text">{selectedLead ? getMemberLabel(selectedLead) : <span className="text-slate-400">Unassigned</span>}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 py-2">
                    <span className="text-text-secondary">Priority</span>
                    <span className={cn('rounded-md px-2 py-0.5 text-xs font-semibold capitalize', priority === 'critical' ? 'bg-red-100 text-red-700' : priority === 'high' ? 'bg-orange-100 text-orange-700' : priority === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-600')}>{priority}</span>
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
            <button type="submit" disabled={loading || !title.trim()} className={primaryButtonClass}>{loading ? 'Saving...' : 'Save Changes'}</button>
          </div>
        </div>
      </form>
    </div>
  )
}
