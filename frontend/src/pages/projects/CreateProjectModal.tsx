import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import type { Project, Priority, Methodology, WorkspaceMember } from '@/types'
import { ArrowRight, Check, Clock, DollarSign, Flag, Layers3, User, X } from 'lucide-react'
import {
  ROLE_LABEL,
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
import type { ProjectRole } from './constants'

type StepId = 'brief' | 'plan' | 'team' | 'review'
type TeamRole = Exclude<ProjectRole, 'lead'>

interface CreateProjectPayload {
  title: string
  description: string
  project_code: string | null
  objective_summary: string | null
  deliverable_output: string | null
  priority: Priority
  methodology: Methodology
  status: Project['status']
  start_date: string | null
  deadline: string | null
  end_date: string | null
  budget: number
  planning_hours: number
  lead_id: string | null
}

const STEP_ORDER: Array<{ id: StepId; label: string; helper: string }> = [
  { id: 'brief', label: 'Project Brief', helper: 'Outcome and methodology' },
  { id: 'plan', label: 'Planning Inputs', helper: 'Dates, status, and resourcing' },
  { id: 'team', label: 'Team Setup', helper: 'Lead and working roles' },
  { id: 'review', label: 'Review', helper: 'Check before create' },
]

const TEAM_ROLES: TeamRole[] = ['contributor', 'reviewer', 'observer']

const STATUS_OPTIONS: Array<{ value: Project['status']; label: string }> = [
  { value: 'planning', label: 'Planning' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'on_hold', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const METHODOLOGY_DETAILS: Record<Methodology, { label: string; summary: string; next: string }> = {
  oppm: {
    label: 'OPPM',
    summary: 'Concise outcome tracking with one-page planning and summary controls.',
    next: 'OPPM View',
  },
  agile: {
    label: 'Agile',
    summary: 'Backlog-first execution with epics, user stories, and sprints.',
    next: 'Agile Board',
  },
  waterfall: {
    label: 'Waterfall',
    summary: 'Phase-gated delivery with structured reviews and supporting documents.',
    next: 'Waterfall Phases',
  },
  hybrid: {
    label: 'Hybrid',
    summary: 'A shared project hub that can branch into OPPM, Agile, and Waterfall setup.',
    next: 'Project Hub',
  },
}

function getDateError(startDate: string, deadline: string, endDate: string): string | null {
  if (startDate && deadline && startDate > deadline) {
    return 'Start date must be on or before the deadline.'
  }
  if (deadline && endDate && deadline > endDate) {
    return 'Deadline must be on or before the end date.'
  }
  if (startDate && endDate && startDate > endDate) {
    return 'Start date must be on or before the end date.'
  }
  return null
}

function getMissingSignals(args: {
  objectiveSummary: string
  deliverableOutput: string
  startDate: string
  deadline: string
  budget: string
  planningHours: string
}) {
  const missing: string[] = []
  if (!args.objectiveSummary.trim()) missing.push('Objective summary')
  if (!args.deliverableOutput.trim()) missing.push('Deliverable output')
  if (!args.startDate) missing.push('Start date')
  if (!args.deadline) missing.push('Deadline')
  if (!args.budget) missing.push('Budget')
  if (!args.planningHours) missing.push('Planning hours')
  return missing
}

export function CreateProjectModal({
  members,
  currentUserId,
  onClose,
  onSubmit,
  loading,
  error,
}: {
  members: WorkspaceMember[]
  currentUserId: string | null
  onClose: () => void
  onSubmit: (data: CreateProjectPayload, memberAssignments: { userId: string; role: string }[]) => void
  loading: boolean
  error?: string | null
}) {
  const creatorMember = members.find((member) => member.user_id === currentUserId)
  const [step, setStep] = useState<StepId>('brief')
  const [title, setTitle] = useState('')
  const [projectCode, setProjectCode] = useState('')
  const [objectiveSummary, setObjectiveSummary] = useState('')
  const [deliverableOutput, setDeliverableOutput] = useState('')
  const [description, setDescription] = useState('')
  const [methodology, setMethodology] = useState<Methodology>('oppm')
  const [status, setStatus] = useState<Project['status']>('planning')
  const [priority, setPriority] = useState<Priority>('medium')
  const [startDate, setStartDate] = useState('')
  const [deadline, setDeadline] = useState('')
  const [endDate, setEndDate] = useState('')
  const [budget, setBudget] = useState('')
  const [planningHours, setPlanningHours] = useState('')
  const [leadId, setLeadId] = useState('')
  const [assignments, setAssignments] = useState<Record<string, TeamRole>>({})
  const [localError, setLocalError] = useState<string | null>(null)

  useEffect(() => {
    if (!leadId && creatorMember) {
      setLeadId(creatorMember.id)
    }
  }, [creatorMember, leadId])

  useEffect(() => {
    setAssignments((prev) => {
      let changed = false
      const next = { ...prev }

      if (creatorMember && next[creatorMember.id]) {
        delete next[creatorMember.id]
        changed = true
      }
      if (leadId && next[leadId]) {
        delete next[leadId]
        changed = true
      }

      return changed ? next : prev
    })
  }, [creatorMember, leadId])

  const currentStepIndex = STEP_ORDER.findIndex((item) => item.id === step)
  const titleError = title.trim() ? null : 'Project name is required.'
  const dateError = getDateError(startDate, deadline, endDate)
  const selectedLead = members.find((member) => member.id === leadId) ?? creatorMember
  const additionalMembers = members.filter((member) => member.id !== creatorMember?.id && member.id !== leadId)
  const selectedMembers = additionalMembers.filter((member) => assignments[member.id])
  const missingSignals = getMissingSignals({
    objectiveSummary,
    deliverableOutput,
    startDate,
    deadline,
    budget,
    planningHours,
  })
  const methodologyDetails = METHODOLOGY_DETAILS[methodology]
  const totalTeamCount = new Set(
    [creatorMember?.id, selectedLead?.id, ...selectedMembers.map((member) => member.id)].filter(Boolean)
  ).size

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

  const setMemberRole = (memberId: string, role: TeamRole) => {
    setAssignments((prev) => ({ ...prev, [memberId]: role }))
  }

  const goToStep = (nextStep: StepId) => {
    if (STEP_ORDER.findIndex((item) => item.id === nextStep) <= currentStepIndex) {
      setLocalError(null)
      setStep(nextStep)
    }
  }

  const handleNext = () => {
    if (step === 'brief' && titleError) {
      setLocalError(titleError)
      return
    }
    if (step === 'plan' && dateError) {
      setLocalError(dateError)
      return
    }
    if (step === 'team' && members.length > 0 && !leadId) {
      setLocalError('Select a project lead before you continue.')
      return
    }

    const nextStep = STEP_ORDER[currentStepIndex + 1]
    if (nextStep) {
      setLocalError(null)
      setStep(nextStep.id)
    }
  }

  const handleBack = () => {
    const previousStep = STEP_ORDER[currentStepIndex - 1]
    if (previousStep) {
      setLocalError(null)
      setStep(previousStep.id)
    }
  }

  const handleSubmit = () => {
    if (titleError) {
      setStep('brief')
      setLocalError(titleError)
      return
    }
    if (dateError) {
      setStep('plan')
      setLocalError(dateError)
      return
    }
    if (members.length > 0 && !leadId) {
      setStep('team')
      setLocalError('Select a project lead before you create the project.')
      return
    }

    const memberAssignments = Object.entries(assignments).map(([userId, role]) => ({ userId, role }))
    const payload: CreateProjectPayload = {
      title: title.trim(),
      description,
      project_code: projectCode || null,
      objective_summary: objectiveSummary || null,
      deliverable_output: deliverableOutput || null,
      priority,
      methodology,
      status,
      start_date: startDate || null,
      deadline: deadline || null,
      end_date: endDate || null,
      budget: budget ? Number(budget) : 0,
      planning_hours: planningHours ? Number(planningHours) : 0,
      lead_id: leadId || null,
    }

    setLocalError(null)
    onSubmit(payload, memberAssignments)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className={modalShellClass} onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="mb-3 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className={sectionEyebrowClass}>Create a project</p>
              <h2 className="text-lg font-semibold text-text">New Project</h2>
              <p className="text-sm text-text-secondary">Capture the project outcome first, then confirm planning inputs, team ownership, and where setup should continue.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-xl p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"><X className="h-4.5 w-4.5" /></button>
          </div>

          <div className="flex flex-wrap gap-2 pb-3">
            {STEP_ORDER.map((item, index) => {
              const isCurrent = step === item.id
              const isDone = index < currentStepIndex
              const isAvailable = index <= currentStepIndex

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => goToStep(item.id)}
                  className={cn(
                    'flex min-w-[10rem] items-center gap-3 rounded-xl border px-3 py-1.5 text-left transition-colors',
                    isCurrent ? 'border-primary/40 bg-primary/5' : isDone ? 'border-primary/20 bg-primary/5' : 'border-border bg-white',
                    !isAvailable && 'cursor-not-allowed opacity-60'
                  )}
                  disabled={!isAvailable}
                >
                  <span className={cn(
                    'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors',
                    isCurrent ? 'bg-primary text-white' : isDone ? 'bg-primary/10 text-primary' : 'bg-slate-100 text-slate-500'
                  )}>
                    {isDone ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span className="min-w-0">
                    <span className={cn('block text-sm font-semibold', isCurrent ? 'text-text' : 'text-text-secondary')}>{item.label}</span>
                    <span className="block text-[11px] text-text-secondary">{item.helper}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6">
          {step === 'brief' ? (
            <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">
              <div className="xl:col-span-3">
                <div className="pb-2 mb-2 border-b border-border">
                  <h3 className="mb-2 text-sm font-semibold text-text">Methodology</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {(Object.keys(METHODOLOGY_DETAILS) as Methodology[]).map((value) => {
                      const details = METHODOLOGY_DETAILS[value]
                      return (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setMethodology(value)}
                          className={cn(
                            'rounded-xl border px-4 py-3 text-left transition-colors',
                            methodology === value ? 'border-primary/40 bg-primary/5 shadow-sm' : 'border-border bg-white hover:border-primary/20 hover:bg-surface-alt'
                          )}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-text">{details.label}</p>
                            {methodology === value && <Check className="h-4 w-4 text-primary" />}
                          </div>
                          <p className="mt-1.5 text-xs leading-5 text-text-secondary">{details.summary}</p>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="pb-2 mb-2 border-b border-border">
                  <h3 className="mb-2 text-sm font-semibold text-text">Project details</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div className="md:col-span-2">
                      <label className={fieldLabelClass}>Project Name <span className="text-red-500">*</span></label>
                      <input value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="e.g. FY2026 platform rollout" className={inputClass} />
                      {titleError && <p className="mt-1.5 text-xs text-red-600">{titleError}</p>}
                    </div>
                    <div>
                      <label className={fieldLabelClass}>Project Code</label>
                      <input value={projectCode} onChange={(e) => setProjectCode(e.target.value)} placeholder="e.g. PRJ-204" maxLength={50} className={inputClass} />
                    </div>
                  </div>
                  <div className="mt-2">
                    <label className={fieldLabelClass}>Objective Summary</label>
                    <input value={objectiveSummary} onChange={(e) => setObjectiveSummary(e.target.value)} placeholder="One clear sentence about the project outcome" className={inputClass} />
                  </div>
                  <div className="mt-2">
                    <label className={fieldLabelClass}>Deliverable Output</label>
                    <input value={deliverableOutput} onChange={(e) => setDeliverableOutput(e.target.value)} placeholder="What tangible output should this project deliver?" className={inputClass} />
                  </div>
                  <div className="mt-2">
                    <label className={fieldLabelClass}>Description</label>
                    <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="Add context, delivery notes, assumptions, or success criteria" className={textareaClass} />
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-3 xl:col-span-2 xl:mt-0">
                <div className="rounded-xl border border-border bg-white p-3 shadow-sm">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">Preview</p>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-text">{title.trim() || 'Untitled project'}</p>
                      <p className="mt-1 text-xs text-text-secondary line-clamp-2">{objectiveSummary.trim() || 'No objective summary yet.'}</p>
                    </div>
                    <span className="shrink-0 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{methodologyDetails.label}</span>
                  </div>
                  <div className="mt-3 divide-y divide-border text-sm">
                    <div className="flex items-center justify-between gap-3 py-1.5">
                      <span className="text-text-secondary">Current Status</span>
                      <span className="font-medium text-text">{STATUS_OPTIONS.find((option) => option.value === status)?.label ?? 'Planning'}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 py-1.5">
                      <span className="text-text-secondary">Deliverable</span>
                      <span className="max-w-[12rem] truncate font-medium text-text">{deliverableOutput.trim() || <span className="text-slate-400">Not defined yet</span>}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 py-1.5">
                      <span className="text-text-secondary">Next stop</span>
                      <span className="font-medium text-text">{methodologyDetails.next}</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2.5">
                  <p className="mb-1.5 text-xs font-semibold text-blue-700">Next: planning inputs</p>
                  <p className="text-xs leading-5 text-blue-600">The next step captures status, dates, and resourcing. Those fields stay guided, but date order is enforced before create.</p>
                </div>
              </div>
            </div>
          ) : step === 'plan' ? (
            <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">
              <div className="xl:col-span-3">
                <section className="pb-2 mb-2 border-b border-border">
                  <h3 className="mb-2 text-sm font-semibold text-text">Execution posture</h3>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    <div>
                      <label className={fieldLabelClass}>Status</label>
                      <select value={status} onChange={(e) => setStatus(e.target.value as Project['status'])} className={selectClass}>
                        {STATUS_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
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
                  </div>
                </section>

                <section className="pb-2 mb-2 border-b border-border">
                  <h3 className="mb-2 text-sm font-semibold text-text">Resources</h3>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
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
                </section>

                <section>
                  <h3 className="mb-2 text-sm font-semibold text-text">Schedule</h3>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                    <div><label className={fieldLabelClass}>Start Date</label><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputClass} /></div>
                    <div><label className={fieldLabelClass}>Deadline</label><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={inputClass} /></div>
                    <div><label className={fieldLabelClass}>End Date</label><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={inputClass} /></div>
                  </div>
                  {dateError && <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{dateError}</p>}
                </section>
              </div>

              <div className="mt-4 space-y-3 xl:col-span-2 xl:mt-0">
                <div className="rounded-xl border border-border bg-white p-3 shadow-sm">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">Planning snapshot</p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                      <span className="text-text-secondary">Status</span>
                      <span className="font-medium text-text">{STATUS_OPTIONS.find((option) => option.value === status)?.label}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                      <span className="text-text-secondary">Priority</span>
                      <span className={cn('rounded-md px-2 py-0.5 text-xs font-semibold capitalize', priority === 'critical' ? 'bg-red-100 text-red-700' : priority === 'high' ? 'bg-orange-100 text-orange-700' : priority === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-600')}>{priority}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                      <span className="text-text-secondary">Budget</span>
                      <span className="font-medium text-text">{budget ? `$${Number(budget).toLocaleString()}` : <span className="text-slate-400">Guided</span>}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                      <span className="text-text-secondary">Planning Hours</span>
                      <span className="font-medium text-text">{planningHours ? `${planningHours} h` : <span className="text-slate-400">Guided</span>}</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2.5">
                  <p className="mb-1.5 text-xs font-semibold text-amber-700">Schedule rules</p>
                  <p className="text-xs leading-5 text-amber-700">The create flow only blocks on invalid chronology: start date cannot be after the deadline, and deadline cannot be after the end date.</p>
                </div>
              </div>
            </div>
          ) : step === 'team' ? (
            <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">
              <div className="xl:col-span-3">
                <section className="pb-2 mb-2 border-b border-border">
                  <h3 className="mb-2 text-sm font-semibold text-text">Project lead</h3>
                  <label className={fieldLabelClass}>Lead</label>
                  <select value={leadId} onChange={(e) => setLeadId(e.target.value)} className={selectClass}>
                    {!creatorMember && <option value="">— Select a lead —</option>}
                    {members.map((member) => (
                      <option key={member.id} value={member.id}>{getMemberLabel(member)}</option>
                    ))}
                  </select>
                  <p className="mt-1.5 text-xs leading-5 text-text-secondary">The creator is the default lead. If you switch the lead, the creator still stays on the project so handoff and ownership are both visible from day one.</p>
                </section>

                <section>
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-text">Additional members</h3>
                      <p className="text-xs text-text-secondary">These roles are for extra workspace members beyond the creator and current lead.</p>
                    </div>
                    <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">{selectedMembers.length} selected</span>
                  </div>

                  {additionalMembers.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-gray-200 py-8 text-center">
                      <User className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                      <p className="text-sm text-text-secondary">No additional workspace members are available for assignment right now.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {additionalMembers.map((member) => {
                        const selected = !!assignments[member.id]
                        return (
                          <div key={member.id} onClick={() => toggleMember(member.id)} className={cn('flex cursor-pointer flex-col gap-3 rounded-lg border px-4 py-3 transition-colors sm:flex-row sm:items-center', selected ? 'border-primary/40 bg-primary/5 shadow-sm' : 'border-border bg-white hover:border-primary/20 hover:bg-surface-alt')}>
                            <div className="flex items-center gap-3">
                              <div className={cn('flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-colors', selected ? 'border-primary bg-primary text-white' : 'border-slate-300 bg-white text-transparent')}><Check className="h-3 w-3" /></div>
                              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{getMemberLabel(member).charAt(0).toUpperCase()}</div>
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-semibold text-text">{getMemberLabel(member)}</p>
                              <p className="text-xs text-text-secondary">{member.email || 'No email on file'}<span className="mx-1.5 text-slate-300">•</span><span className="capitalize">Workspace {member.role}</span></p>
                            </div>
                            {selected && (
                              <select value={assignments[member.id]} onClick={(e) => e.stopPropagation()} onChange={(e) => { e.stopPropagation(); setMemberRole(member.id, e.target.value as TeamRole) }} className="w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm font-medium outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 sm:w-44">
                                {TEAM_ROLES.map((role) => <option key={role} value={role}>{ROLE_LABEL[role]}</option>)}
                              </select>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </section>
              </div>

              <div className="mt-4 space-y-3 xl:col-span-2 xl:mt-0">
                <div className="rounded-xl border border-border bg-white p-3 shadow-sm">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Team summary</p>
                    <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">{totalTeamCount} people</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
                      <span className="text-text-secondary">Lead</span>
                      <span className="font-medium text-text">{selectedLead ? getMemberLabel(selectedLead) : 'Unassigned'}</span>
                    </div>
                    {creatorMember && (
                      <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
                        <span className="text-text-secondary">Creator</span>
                        <span className="font-medium text-text">{selectedLead?.id === creatorMember.id ? 'Lead' : 'Contributor'}</span>
                      </div>
                    )}
                    {selectedMembers.length === 0 ? (
                      <p className="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-text-secondary">No additional members selected yet.</p>
                    ) : (
                      selectedMembers.map((member) => (
                        <div key={member.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
                          <span className="min-w-0 truncate font-medium text-text">{getMemberLabel(member)}</span>
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{ROLE_LABEL[assignments[member.id]]}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2.5">
                  <p className="mb-1.5 text-xs font-semibold text-blue-700">Team input rules</p>
                  <p className="text-xs leading-5 text-blue-600">This setup only accepts current workspace members. The lead is a single explicit selection. Additional members are limited to contributor, reviewer, or observer roles here.</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-5">
              <div className="xl:col-span-3">
                <div className="rounded-xl border border-border bg-white p-3 shadow-sm">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Review</p>
                      <h3 className="mt-1 text-base font-semibold text-text">Create the project with this setup</h3>
                    </div>
                    <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">{methodologyDetails.label}</span>
                  </div>

                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    <div className="rounded-lg border border-border px-3 py-2.5">
                      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Outcome</p>
                      <p className="mt-1.5 text-sm font-semibold text-text">{title.trim() || 'Untitled project'}</p>
                      <p className="mt-1 text-sm text-text-secondary">{objectiveSummary.trim() || 'No objective summary yet.'}</p>
                      <p className="mt-1.5 text-sm text-text-secondary"><span className="font-medium text-text">Deliverable:</span> {deliverableOutput.trim() || 'Not defined yet'}</p>
                    </div>
                    <div className="rounded-lg border border-border px-3 py-2.5">
                      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Planning</p>
                      <div className="mt-1.5 space-y-1.5 text-sm text-text-secondary">
                        <p><span className="font-medium text-text">Status:</span> {STATUS_OPTIONS.find((option) => option.value === status)?.label}</p>
                        <p><span className="font-medium text-text">Priority:</span> {priority}</p>
                        <p><span className="font-medium text-text">Budget:</span> {budget ? `$${Number(budget).toLocaleString()}` : 'Not set'}</p>
                        <p><span className="font-medium text-text">Planning Hours:</span> {planningHours ? `${planningHours} h` : 'Not set'}</p>
                      </div>
                    </div>
                    <div className="rounded-lg border border-border px-3 py-2.5">
                      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Schedule</p>
                      <div className="mt-1.5 space-y-1.5 text-sm text-text-secondary">
                        <p><span className="font-medium text-text">Start:</span> {startDate || 'Not set'}</p>
                        <p><span className="font-medium text-text">Deadline:</span> {deadline || 'Not set'}</p>
                        <p><span className="font-medium text-text">End:</span> {endDate || 'Not set'}</p>
                      </div>
                    </div>
                    <div className="rounded-lg border border-border px-3 py-2.5">
                      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Team</p>
                      <div className="mt-1.5 space-y-1.5 text-sm text-text-secondary">
                        <p><span className="font-medium text-text">Lead:</span> {selectedLead ? getMemberLabel(selectedLead) : 'Unassigned'}</p>
                        <p><span className="font-medium text-text">Members:</span> {totalTeamCount}</p>
                        <p><span className="font-medium text-text">Additional roles:</span> {selectedMembers.length > 0 ? selectedMembers.map((member) => `${getMemberLabel(member)} (${ROLE_LABEL[assignments[member.id]]})`).join(', ') : 'None selected'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-3 xl:col-span-2 xl:mt-0">
                <div className="rounded-xl border border-border bg-white p-3 shadow-sm">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">Where setup continues</p>
                  <div className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2.5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text">{methodologyDetails.next}</p>
                        <p className="mt-1 text-xs leading-5 text-text-secondary">{methodologyDetails.summary}</p>
                      </div>
                      <ArrowRight className="h-4 w-4 shrink-0 text-primary" />
                    </div>
                  </div>
                  <div className="mt-3 space-y-1.5 text-sm text-text-secondary">
                    <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
                      <Layers3 className="h-4 w-4 text-primary" />
                      <span>{methodologyDetails.label} setup opens immediately after create.</span>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
                      <Flag className="h-4 w-4 text-primary" />
                      <span>The lead and selected team roles are saved as part of the initial project shell.</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2.5">
                  <p className="mb-1.5 text-xs font-semibold text-amber-700">Recommended but optional</p>
                  {missingSignals.length === 0 ? (
                    <p className="text-xs leading-5 text-amber-700">All recommended fields for the initial project shell are covered.</p>
                  ) : (
                    <p className="text-xs leading-5 text-amber-700">You can create this now, but these planning signals are still blank: {missingSignals.join(', ')}.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 border-t border-border bg-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text">{step === 'brief' ? 'Start with the outcome and delivery style' : step === 'plan' ? 'Set the working envelope for this project' : step === 'team' ? 'Confirm the people who will carry the work' : 'Check the setup before the project is created'}</p>
            <p className="hidden text-xs text-text-secondary sm:block">{step === 'brief' ? 'A clear title, methodology, and intended deliverable make the follow-up setup much easier.' : step === 'plan' ? 'Dates are guided, not required, but invalid chronology is blocked.' : step === 'team' ? 'The creator stays on the project automatically. You only need to choose extra members and the lead.' : `The project will open in ${methodologyDetails.next} right after create.`}</p>
            {(localError || error) && <p className="mt-1 text-sm text-red-600">{localError || error}</p>}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <button type="button" onClick={onClose} className={secondaryButtonClass}>Cancel</button>
            {step !== 'brief' && <button type="button" onClick={handleBack} className={secondaryButtonClass}>Back</button>}
            {step === 'review' ? (
              <button type="button" disabled={loading} onClick={handleSubmit} className={primaryButtonClass}>{loading ? 'Creating...' : `Create and Open ${methodologyDetails.next}`}</button>
            ) : (
              <button type="button" onClick={handleNext} className={primaryButtonClass}>{step === 'brief' ? 'Next: Planning Inputs' : step === 'plan' ? 'Next: Team Setup' : 'Next: Review'}</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}