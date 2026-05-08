import type { WorkspaceMember } from '@/types'

export const PROJECT_ROLES = ['lead', 'contributor', 'reviewer', 'observer'] as const
export type ProjectRole = typeof PROJECT_ROLES[number]

export const ROLE_LABEL: Record<ProjectRole, string> = {
  lead: 'Lead',
  contributor: 'Contributor',
  reviewer: 'Reviewer',
  observer: 'Observer',
}

export const fieldLabelClass = 'mb-1.5 block text-sm font-medium text-text-secondary'
export const inputClass = 'w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10'
export const selectClass = 'w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10'
export const textareaClass = 'w-full rounded-lg border border-border bg-white px-3.5 py-2 text-sm text-text outline-none transition-colors placeholder:text-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/10 resize-none'
export const sectionClass = ''
export const sectionEyebrowClass = 'text-[11px] font-semibold uppercase tracking-[0.14em] text-text-secondary'
export const modalShellClass = 'flex max-h-[92vh] w-[min(58rem,calc(100vw-1rem))] flex-col overflow-hidden rounded-2xl border border-border bg-white shadow-2xl'
export const secondaryButtonClass = 'rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-alt'
export const primaryButtonClass = 'inline-flex items-center justify-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50'

export function getMemberLabel(member: WorkspaceMember) {
  return member.display_name || member.email || member.user_id.slice(0, 8)
}
