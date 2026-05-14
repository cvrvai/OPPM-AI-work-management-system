import { cn } from '@/lib/utils'

export interface TaskOwnerAssignment {
  member_id: string
  priority: 'A' | 'B' | 'C'
}

interface ProjectAllMemberOption {
  id: string
  member_id: string
  source: 'workspace' | 'virtual'
  name: string
  is_leader: boolean
}

interface TaskOwnerEditorProps {
  members: ProjectAllMemberOption[]
  assignments: TaskOwnerAssignment[]
  onChange: (assignments: TaskOwnerAssignment[]) => void
}

const PRIORITY_ROWS: Array<{ priority: 'A' | 'B' | 'C'; label: string; description: string }> = [
  { priority: 'A', label: 'Primary owner', description: 'Main accountable owner for the OPPM row.' },
  { priority: 'B', label: 'Primary helper', description: 'Key helper for delivery support.' },
  { priority: 'C', label: 'Secondary helper', description: 'Optional secondary support owner.' },
]

export function TaskOwnerEditor({ members, assignments, onChange }: TaskOwnerEditorProps) {
  const selectedByPriority = new Map(assignments.map((assignment) => [assignment.priority, assignment.member_id]))

  const handlePriorityChange = (priority: 'A' | 'B' | 'C', memberId: string) => {
    const nextAssignments = assignments.filter(
      (assignment) => assignment.priority !== priority && assignment.member_id !== memberId,
    )
    if (memberId) {
      nextAssignments.push({ priority, member_id: memberId })
    }
    nextAssignments.sort((left, right) => left.priority.localeCompare(right.priority))
    onChange(nextAssignments)
  }

  if (members.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm text-text-secondary">
        Add project members before assigning A/B/C owners.
      </div>
    )
  }

  return (
    <div className="space-y-2.5 rounded-xl border border-border bg-surface-alt/40 p-3">
      {PRIORITY_ROWS.map((row) => {
        const selectedMemberId = selectedByPriority.get(row.priority) ?? ''
        return (
          <div key={row.priority} className="grid grid-cols-1 gap-2 rounded-xl border border-border bg-white p-2.5 sm:grid-cols-[auto,1fr] sm:items-center">
            <div className="space-y-1 sm:w-32">
              <span className={cn(
                'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold tracking-[0.12em]',
                row.priority === 'A' ? 'bg-emerald-100 text-emerald-700' : row.priority === 'B' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700',
              )}>
                {row.priority}
              </span>
              <p className="text-sm font-semibold text-text">{row.label}</p>
              <p className="text-xs text-text-secondary">{row.description}</p>
            </div>
            <select
              value={selectedMemberId}
              onChange={(event) => handlePriorityChange(row.priority, event.target.value)}
              className="w-full rounded-xl border border-border bg-white px-3.5 py-2.5 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10"
            >
              <option value="">None</option>
              {members.map((member) => {
                const selectedElsewhere = assignments.some(
                  (assignment) => assignment.priority !== row.priority && assignment.member_id === member.id,
                )
                return (
                  <option key={member.id} value={member.id} disabled={selectedElsewhere}>
                    {member.name}{member.is_leader ? ' (Leader)' : ''}
                  </option>
                )
              })}
            </select>
          </div>
        )
      })}
    </div>
  )
}