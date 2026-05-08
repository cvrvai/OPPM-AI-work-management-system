import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { WorkspaceInvite, WorkspaceMember, WorkspaceRole } from '@/types'
import {
  Loader2,
  Users,
  Search,
  UserPlus,
  UserCheck,
  AlertTriangle,
  Trash2,
  RefreshCw,
  Clock,
  Mail,
  Crown,
  Shield,
  Eye,
  CheckCircle2,
} from 'lucide-react'
import { cn, getInitials } from '@/lib/utils'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const ROLE_CONFIG: Record<WorkspaceRole, { label: string; color: string; icon: typeof Crown; description: string }> = {
  owner:  { label: 'Owner',  color: 'bg-amber-100 text-amber-700',  icon: Crown,  description: 'Full control including deleting the workspace' },
  admin:  { label: 'Admin',  color: 'bg-purple-100 text-purple-700', icon: Shield, description: 'Manage members, settings, and all projects' },
  member: { label: 'Member', color: 'bg-blue-100 text-blue-700',    icon: Users,  description: 'Create projects, manage own tasks, comment' },
  viewer: { label: 'Viewer', color: 'bg-gray-100 text-gray-600',    icon: Eye,    description: 'Read-only access — great for clients or auditors' },
}

const ROLE_ORDER: WorkspaceRole[] = ['owner', 'admin', 'member', 'viewer']

type EmailLookup = { exists: boolean; user_id?: string; display_name?: string; already_member: boolean }

export function WorkspaceMembersPanel() {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const user = useAuthStore((s) => s.user)
  const wsPath = `/v1/workspaces/${ws!.id}`
  const currentRole = ws?.current_user_role ?? ws?.role
  const isAdmin = currentRole === 'owner' || currentRole === 'admin'
  const [inviteReferenceTime] = useState(() => Date.now())

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<WorkspaceRole>('member')
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)
  const [memberSearch, setMemberSearch] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [lookupState, setLookupState] = useState<'idle' | 'loading' | 'found' | 'not-found' | 'member'>('idle')
  const [lookupData, setLookupData] = useState<EmailLookup | null>(null)

  const handleInviteEmailChange = (value: string) => {
    setInviteEmail(value)
    const trimmed = value.trim()
    if (!trimmed || !EMAIL_PATTERN.test(trimmed)) {
      setLookupState('idle')
      setLookupData(null)
      return
    }
    setLookupState('loading')
  }

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const trimmed = inviteEmail.trim()
    if (!trimmed || !EMAIL_PATTERN.test(trimmed)) return

    debounceRef.current = setTimeout(async () => {
      try {
        const result = await api.get<EmailLookup>(
          `${wsPath}/members/lookup?email=${encodeURIComponent(trimmed)}`
        )
        setLookupData(result)
        if (result.already_member) setLookupState('member')
        else if (result.exists) setLookupState('found')
        else setLookupState('not-found')
      } catch {
        setLookupState('idle')
      }
    }, 500)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [inviteEmail, wsPath])

  const { data: members = [], isLoading: loadingMembers } = useQuery({
    queryKey: ['workspace-members', ws?.id],
    queryFn: () => api.get<WorkspaceMember[]>(`${wsPath}/members`),
    enabled: !!ws,
  })

  const { data: invites = [], isLoading: loadingInvites } = useQuery({
    queryKey: ['workspace-invites', ws?.id],
    queryFn: () => api.get<WorkspaceInvite[]>(`${wsPath}/invites`),
    enabled: !!ws && isAdmin,
  })

  const sendInvite = useMutation({
    mutationFn: (data: { email: string; role: string }) => api.post(`${wsPath}/invites`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-invites', ws?.id] })
      setInviteEmail('')
      setInviteRole('member')
      setLookupState('idle')
      setLookupData(null)
    },
  })

  const updateRole = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      api.put(`${wsPath}/members/${memberId}`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-members', ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
    },
  })

  const removeMember = useMutation({
    mutationFn: (memberId: string) => api.delete(`${wsPath}/members/${memberId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-members', ws?.id] })
      setConfirmRemove(null)
    },
  })

  const revokeInvite = useMutation({
    mutationFn: (inviteId: string) => api.delete(`${wsPath}/invites/${inviteId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workspace-invites', ws?.id] }),
  })

  const resendInvite = useMutation({
    mutationFn: (inviteId: string) => api.post(`${wsPath}/invites/${inviteId}/resend`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workspace-invites', ws?.id] }),
  })

  const ownerCount = members.filter(m => m.role === 'owner').length
  const sortedMembers = [...members].sort(
    (a, b) => ROLE_ORDER.indexOf(a.role as WorkspaceRole) - ROLE_ORDER.indexOf(b.role as WorkspaceRole)
  )
  const filteredMembers = memberSearch.trim()
    ? sortedMembers.filter(m =>
        (m.display_name || '').toLowerCase().includes(memberSearch.toLowerCase()) ||
        (m.email || '').toLowerCase().includes(memberSearch.toLowerCase())
      )
    : sortedMembers

  const canSendInvite = lookupState !== 'member' && lookupState !== 'loading' && inviteEmail.trim()
  const isNewUser = lookupState === 'not-found'

  return (
    <div className="space-y-6">
      {isAdmin && (
        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-text mb-4 flex items-center gap-2">
            <UserPlus className="h-4 w-4 text-primary" />
            Invite Member
          </h2>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!canSendInvite) return
              sendInvite.mutate({ email: inviteEmail.trim(), role: inviteRole })
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Email address</label>
              <div className="relative">
                <input
                  type="email"
                  placeholder="colleague@company.com"
                  value={inviteEmail}
                  onChange={(e) => handleInviteEmailChange(e.target.value)}
                  required
                  className={cn(
                    'w-full rounded-lg border px-3 py-2 text-sm pr-10 outline-none focus:ring-2 transition-all',
                    lookupState === 'found'     && 'border-emerald-400 focus:border-emerald-500 focus:ring-emerald-100',
                    lookupState === 'not-found' && 'border-amber-400 focus:border-amber-500 focus:ring-amber-100',
                    lookupState === 'member'    && 'border-danger focus:border-danger focus:ring-danger/10',
                    (lookupState === 'idle' || lookupState === 'loading') && 'border-border focus:border-primary focus:ring-primary/20',
                  )}
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  {lookupState === 'loading' && <Loader2 className="h-4 w-4 animate-spin text-text-secondary" />}
                  {lookupState === 'found'   && <UserCheck className="h-4 w-4 text-emerald-500" />}
                  {lookupState === 'not-found' && <AlertTriangle className="h-4 w-4 text-amber-500" />}
                  {lookupState === 'member'  && <AlertTriangle className="h-4 w-4 text-danger" />}
                </div>
              </div>

              {lookupState === 'found' && lookupData && (
                <div className="mt-2 flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-sm text-emerald-700">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-200 text-emerald-700 text-xs font-semibold">
                    {getInitials(lookupData.display_name || inviteEmail)}
                  </div>
                  <span><strong>{lookupData.display_name || inviteEmail}</strong> has an account — they'll receive an invite email.</span>
                </div>
              )}
              {lookupState === 'not-found' && (
                <div className="mt-2 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-700">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>No account found. They'll receive a <strong>sign-up link</strong> — they can register and join automatically.</span>
                </div>
              )}
              {lookupState === 'member' && (
                <div className="mt-2 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-danger">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>This person is already a member of this workspace.</span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Assign role</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {(['admin', 'member', 'viewer'] as WorkspaceRole[]).map((role) => {
                  const cfg = ROLE_CONFIG[role]
                  const Icon = cfg.icon
                  return (
                    <button
                      key={role}
                      type="button"
                      onClick={() => setInviteRole(role)}
                      className={cn(
                        'flex flex-col items-start gap-1 rounded-lg border-2 px-3 py-2.5 text-left transition-all',
                        inviteRole === role
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-text-secondary/50'
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        <Icon className={cn('h-3.5 w-3.5', inviteRole === role ? 'text-primary' : 'text-text-secondary')} />
                        <span className={cn('text-sm font-semibold', inviteRole === role ? 'text-primary' : 'text-text')}>
                          {cfg.label}
                        </span>
                        {role === 'member' && (
                          <span className="ml-1 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">recommended</span>
                        )}
                      </div>
                      <p className="text-[11px] text-text-secondary leading-tight">{cfg.description}</p>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={sendInvite.isPending || !canSendInvite}
                className="rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50 transition-colors"
              >
                {sendInvite.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : isNewUser ? (
                  'Send Sign-Up Invite'
                ) : (
                  'Send Invite'
                )}
              </button>
              {sendInvite.isError && (
                <p className="text-sm text-danger">{(sendInvite.error as Error).message}</p>
              )}
              {sendInvite.isSuccess && (
                <p className="text-sm text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="h-4 w-4" /> Invitation sent!
                </p>
              )}
            </div>
          </form>
        </div>
      )}

      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" />
            Members
            <span className="text-xs text-text-secondary font-normal">({members.length})</span>
          </h2>
          {members.length > 5 && (
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-secondary pointer-events-none" />
              <input
                value={memberSearch}
                onChange={(e) => setMemberSearch(e.target.value)}
                placeholder="Search members..."
                className="rounded-lg border border-border pl-8 pr-3 py-1.5 text-xs outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 w-44"
              />
            </div>
          )}
        </div>
        {loadingMembers ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredMembers.map((member) => {
              const isSelf = member.user_id === user?.id
              const isLastOwner = member.role === 'owner' && ownerCount <= 1
              const roleInfo = ROLE_CONFIG[member.role as WorkspaceRole] || ROLE_CONFIG.member
              const RoleIcon = roleInfo.icon

              return (
                <div key={member.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                      {getInitials(member.display_name || member.email || '?')}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-text">
                        {member.display_name || member.email || member.user_id.slice(0, 8)}
                        {isSelf && <span className="ml-1.5 text-xs text-text-secondary">(you)</span>}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-text-secondary">
                        {member.email && member.display_name && <span>{member.email}</span>}
                        {member.joined_at && (
                          <span className="text-text-secondary/60">
                            · since {new Date(member.joined_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {isAdmin && !isSelf && !isLastOwner ? (
                      <select
                        value={member.role}
                        onChange={(e) => updateRole.mutate({ memberId: member.id, role: e.target.value })}
                        className="rounded-lg border border-border px-2 py-1 text-xs outline-none focus:border-primary"
                      >
                        <option value="owner">Owner</option>
                        <option value="admin">Admin</option>
                        <option value="member">Member</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    ) : (
                      <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium', roleInfo.color)}>
                        <RoleIcon className="h-3 w-3" />
                        {roleInfo.label}
                      </span>
                    )}
                    {isAdmin && !isSelf && !isLastOwner && (
                      confirmRemove === member.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => removeMember.mutate(member.id)}
                            disabled={removeMember.isPending}
                            className="rounded px-2 py-1 text-xs font-medium bg-danger text-white hover:bg-red-700"
                          >
                            Confirm
                          </button>
                          <button
                            onClick={() => setConfirmRemove(null)}
                            className="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-alt"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmRemove(member.id)}
                          className="text-text-secondary hover:text-danger transition-colors"
                          title="Remove member"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )
                    )}
                  </div>
                </div>
              )
            })}
            {filteredMembers.length === 0 && (
              <p className="py-6 text-center text-sm text-text-secondary">No members match your search.</p>
            )}
          </div>
        )}
      </div>

      {isAdmin && (
        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-text mb-4 flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />
            Pending Invites
            {invites.length > 0 && (
              <span className="text-xs text-text-secondary font-normal">({invites.length})</span>
            )}
          </h2>
          {loadingInvites ? (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
            </div>
          ) : invites.length === 0 ? (
            <p className="text-sm text-text-secondary text-center py-6">No pending invitations</p>
          ) : (
            <div className="divide-y divide-border">
              {invites.map((invite) => {
                const expiresAt = new Date(invite.expires_at)
                const isExpired = expiresAt.getTime() < inviteReferenceTime
                const daysLeft = Math.max(0, Math.ceil((expiresAt.getTime() - inviteReferenceTime) / (1000 * 60 * 60 * 24)))
                const sentAt = invite.sent_at ? new Date(invite.sent_at) : null
                const isNew = invite.is_new_user
                const roleInfo = ROLE_CONFIG[invite.role] || ROLE_CONFIG.member

                return (
                  <div key={invite.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gray-100 text-gray-500">
                        <Mail className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-text">{invite.email}</p>
                          {isNew === true && (
                            <span className="rounded-full bg-amber-100 text-amber-700 px-1.5 py-0.5 text-[10px] font-medium">new user</span>
                          )}
                          {isNew === false && (
                            <span className="rounded-full bg-blue-100 text-blue-700 px-1.5 py-0.5 text-[10px] font-medium">existing user</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-text-secondary mt-0.5">
                          <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium', roleInfo.color)}>
                            {roleInfo.label}
                          </span>
                          {sentAt && <span>sent {sentAt.toLocaleDateString()}</span>}
                          {isExpired ? (
                            <span className="text-danger font-medium">· Expired</span>
                          ) : (
                            <span className={cn(daysLeft <= 1 ? 'text-danger' : daysLeft <= 3 ? 'text-amber-600' : '')}>
                              · {daysLeft}d left
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => resendInvite.mutate(invite.id)}
                        disabled={resendInvite.isPending}
                        className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:text-primary hover:border-primary transition-colors"
                        title="Resend invite"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        Resend
                      </button>
                      <button
                        onClick={() => revokeInvite.mutate(invite.id)}
                        disabled={revokeInvite.isPending}
                        className="text-text-secondary hover:text-danger transition-colors"
                        title="Revoke invite"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
