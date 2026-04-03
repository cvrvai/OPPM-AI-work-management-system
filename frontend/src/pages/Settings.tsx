import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { GitAccount, RepoConfig, AIModel, Project, WorkspaceMember, WorkspaceInvite, WorkspaceRole } from '@/types'
import {
  GitFork,
  Plus,
  Trash2,
  Check,
  Cpu,
  Globe,
  Key,
  UserCircle,
  Loader2,
  Copy,
  CheckCircle2,
  Users,
  Mail,
  Shield,
  Crown,
  Eye,
  Clock,
  AlertTriangle,
  UserCheck,
  RefreshCw,
  Search,
  UserPlus,
} from 'lucide-react'
import { cn, getInitials } from '@/lib/utils'
import { useChatContext } from '@/hooks/useChatContext'

export function Settings() {
  const [activeTab, setActiveTab] = useState<'profile' | 'members' | 'github' | 'ai'>('profile')
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  useChatContext('workspace')

  const navItems = [
    { id: 'profile'  as const, label: 'Profile',              icon: UserCircle, description: 'Name, email and account info' },
    ...(ws ? [{ id: 'members' as const, label: 'Members', icon: Users, description: 'Invite and manage workspace members' }] : []),
    { id: 'github'   as const, label: 'GitHub Integration',   icon: GitFork,    description: 'Connect repos and configure webhooks' },
    { id: 'ai'       as const, label: 'AI Models',            icon: Cpu,        description: 'LLM providers and API keys' },
  ]

  const active = navItems.find((n) => n.id === activeTab) ?? navItems[0]

  return (
    <div className="flex gap-8 min-h-[calc(100vh-120px)]">
      {/* ── Left sidebar nav ── */}
      <aside className="w-56 shrink-0">
        <div className="mb-5">
          <h1 className="text-xl font-bold text-text">Settings</h1>
          <p className="text-xs text-text-secondary mt-0.5 leading-relaxed">
            Configure your workspace
          </p>
        </div>
        <nav className="space-y-0.5">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                'w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-left transition-colors',
                activeTab === id
                  ? 'bg-primary/10 text-primary'
                  : 'text-text-secondary hover:bg-surface-alt hover:text-text'
              )}
            >
              <Icon className={cn('h-4 w-4 shrink-0', activeTab === id ? 'text-primary' : 'text-text-secondary')} />
              {label}
            </button>
          ))}
        </nav>
      </aside>

      {/* ── Divider ── */}
      <div className="w-px bg-border shrink-0" />

      {/* ── Content panel ── */}
      <div className="flex-1 min-w-0">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-text flex items-center gap-2">
            <active.icon className="h-5 w-5 text-primary" />
            {active.label}
          </h2>
          <p className="text-sm text-text-secondary mt-0.5">{active.description}</p>
        </div>

        {activeTab === 'profile'  && <ProfileSettings />}
        {activeTab === 'members'  && ws && <MembersSettings />}
        {activeTab === 'github'   && <GitHubSettings />}
        {activeTab === 'ai'       && <AIModelSettings />}
      </div>
    </div>
  )
}

function ProfileSettings() {
  const user = useAuthStore((s) => s.user)
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const email = user?.email || ''
  const name = user?.user_metadata?.full_name || email.split('@')[0]
  const [displayName, setDisplayName] = useState(name)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      // Update profile via gateway → core auth endpoint
      await api.patch('/auth/profile', { full_name: displayName })
      // Also update workspace_members.display_name if workspace is selected
      if (ws) {
        await api.patch(`/v1/workspaces/${ws.id}/members/me/display-name`, {
          display_name: displayName,
        })
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-text mb-6">Profile Information</h2>
        <div className="flex items-start gap-6">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary text-white text-2xl font-bold shrink-0">
            {getInitials(displayName || 'U')}
          </div>
          <div className="flex-1 space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Display Name</label>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full max-w-sm rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Email</label>
              <input
                value={email}
                disabled
                className="w-full max-w-sm rounded-lg border border-border bg-surface-alt px-3 py-2 text-sm text-text-secondary cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">User ID</label>
              <input
                value={user?.id || ''}
                disabled
                className="w-full max-w-sm rounded-lg border border-border bg-surface-alt px-3 py-2 text-xs font-mono text-text-secondary cursor-not-allowed"
              />
            </div>
            <button
              onClick={handleSave}
              disabled={saving || displayName === name}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50 transition-colors"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : saved ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : null}
              {saved ? 'Saved!' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-text mb-4">Account</h2>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between py-2 border-b border-border">
            <span className="text-text-secondary">Created</span>
            <span className="text-text">{user?.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-border">
            <span className="text-text-secondary">Last Sign In</span>
            <span className="text-text">{user?.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleDateString() : '-'}</span>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-text-secondary">Auth Provider</span>
            <span className="text-text capitalize">{user?.app_metadata?.provider || 'email'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Members & Invites ──

type EmailLookup = { exists: boolean; user_id?: string; display_name?: string; already_member: boolean }

const ROLE_CONFIG: Record<WorkspaceRole, { label: string; color: string; icon: typeof Crown; description: string }> = {
  owner:  { label: 'Owner',  color: 'bg-amber-100 text-amber-700',  icon: Crown,  description: 'Full control including deleting the workspace' },
  admin:  { label: 'Admin',  color: 'bg-purple-100 text-purple-700', icon: Shield, description: 'Manage members, settings, and all projects' },
  member: { label: 'Member', color: 'bg-blue-100 text-blue-700',    icon: Users,  description: 'Create projects, manage own tasks, comment' },
  viewer: { label: 'Viewer', color: 'bg-gray-100 text-gray-600',    icon: Eye,    description: 'Read-only access — great for clients or auditors' },
}

const ROLE_ORDER: WorkspaceRole[] = ['owner', 'admin', 'member', 'viewer']

function MembersSettings() {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const user = useAuthStore((s) => s.user)
  const wsPath = `/v1/workspaces/${ws!.id}`
  const currentRole = (ws as any)?.current_user_role as WorkspaceRole | undefined
  const isAdmin = currentRole === 'owner' || currentRole === 'admin'

  // ── Invite form state ──
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<WorkspaceRole>('member')
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)
  const [memberSearch, setMemberSearch] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Email lookup ──
  const [lookupState, setLookupState] = useState<'idle' | 'loading' | 'found' | 'not-found' | 'member'>('idle')
  const [lookupData, setLookupData] = useState<EmailLookup | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const trimmed = inviteEmail.trim()
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setLookupState('idle')
      setLookupData(null)
      return
    }
    setLookupState('loading')
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

  // ── Queries ──
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

  // ── Mutations ──
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
      {/* ── Invite Form (admin+ only) ── */}
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
            {/* Email input + lookup feedback */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Email address</label>
              <div className="relative">
                <input
                  type="email"
                  placeholder="colleague@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
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

              {/* Lookup status banner */}
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

            {/* Role picker cards */}
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

      {/* ── Members List ── */}
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

      {/* ── Pending Invites (admin+ only) ── */}
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
                const isExpired = expiresAt < new Date()
                const daysLeft = Math.max(0, Math.ceil((expiresAt.getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
                const sentAt = (invite as any).sent_at ? new Date((invite as any).sent_at) : null
                const isNew = (invite as any).is_new_user as boolean | undefined
                const roleInfo = ROLE_CONFIG[invite.role as WorkspaceRole] || ROLE_CONFIG.member

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

function GitHubSettings() {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [showAddRepo, setShowAddRepo] = useState(false)
  const [accountName, setAccountName] = useState('')
  const [githubUsername, setGithubUsername] = useState('')
  const [token, setToken] = useState('')
  const [repoName, setRepoName] = useState('')
  const [repoProjectId, setRepoProjectId] = useState('')
  const [repoAccountId, setRepoAccountId] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [copied, setCopied] = useState(false)

  const { data: accounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ['github-accounts', ws?.id],
    queryFn: () => api.get<GitAccount[]>(`${wsPath}/github-accounts`),
    enabled: !!ws,
  })

  const { data: repos, isLoading: loadingRepos } = useQuery({
    queryKey: ['repo-configs', ws?.id],
    queryFn: () => api.get<RepoConfig[]>(`${wsPath}/git/repos`),
    enabled: !!ws,
  })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      const res = await api.get<{ items: Project[]; total: number }>(`${wsPath}/projects`)
      return (res as any)?.items ?? []
    },
    enabled: !!ws,
  })

  const createAccount = useMutation({
    mutationFn: (data: { account_name: string; github_username: string; token: string }) =>
      api.post(`${wsPath}/github-accounts`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-accounts'] })
      setShowAddAccount(false)
      setAccountName('')
      setGithubUsername('')
      setToken('')
    },
  })

  const deleteAccount = useMutation({
    mutationFn: (id: string) => api.delete(`${wsPath}/github-accounts/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['github-accounts'] }),
  })

  const createRepo = useMutation({
    mutationFn: (data: { repo_name: string; project_id: string; github_account_id: string; webhook_secret: string }) =>
      api.post(`${wsPath}/git/repos`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repo-configs'] })
      setShowAddRepo(false)
      setRepoName('')
      setRepoProjectId('')
      setRepoAccountId('')
      setWebhookSecret('')
    },
  })

  const deleteRepo = useMutation({
    mutationFn: (id: string) => api.delete(`${wsPath}/git/repos/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['repo-configs'] }),
  })

  const accs = accounts || []
  const rps = repos || []

  const handleCopyWebhook = () => {
    navigator.clipboard.writeText(`${window.location.origin}/api/git/webhook`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* GitHub Accounts */}
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">GitHub Accounts</h2>
          <button
            onClick={() => setShowAddAccount(!showAddAccount)}
            className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark"
          >
            <Plus className="h-3.5 w-3.5" /> Add Account
          </button>
        </div>

        {showAddAccount && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              createAccount.mutate({ account_name: accountName, github_username: githubUsername, token })
            }}
            className="mb-4 rounded-lg border border-border bg-surface-alt p-4 space-y-3"
          >
            <div className="grid grid-cols-3 gap-3">
              <input
                placeholder="Account name"
                value={accountName}
                onChange={(e) => setAccountName(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                placeholder="GitHub username"
                value={githubUsername}
                onChange={(e) => setGithubUsername(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                placeholder="Personal Access Token"
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddAccount(false)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createAccount.isPending}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
              >
                {createAccount.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        )}

        {loadingAccounts ? (
          <div className="flex justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : accs.length === 0 ? (
          <p className="text-sm text-text-secondary text-center py-6">No GitHub accounts configured</p>
        ) : (
          <div className="space-y-2">
            {accs.map((acc) => (
              <div key={acc.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div className="flex items-center gap-3">
                  <GitFork className="h-5 w-5 text-text-secondary" />
                  <div>
                    <p className="text-sm font-medium text-text">{acc.account_name}</p>
                    <p className="text-xs text-text-secondary">@{acc.github_username}</p>
                  </div>
                </div>
                <button
                  onClick={() => deleteAccount.mutate(acc.id)}
                  disabled={deleteAccount.isPending}
                  className="text-text-secondary hover:text-danger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Repository Configs */}
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">Repository Configurations</h2>
          <button
            onClick={() => setShowAddRepo(!showAddRepo)}
            className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark"
          >
            <Plus className="h-3.5 w-3.5" /> Add Repo
          </button>
        </div>

        {showAddRepo && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              createRepo.mutate({
                repo_name: repoName,
                project_id: repoProjectId,
                github_account_id: repoAccountId,
                webhook_secret: webhookSecret,
              })
            }}
            className="mb-4 rounded-lg border border-border bg-surface-alt p-4 space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <input
                placeholder="owner/repo-name"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                placeholder="Webhook Secret (min 8 chars)"
                value={webhookSecret}
                onChange={(e) => setWebhookSecret(e.target.value)}
                required
                minLength={8}
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <select
                value={repoProjectId}
                onChange={(e) => setRepoProjectId(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="">Select project...</option>
                {(projects || []).map((p) => (
                  <option key={p.id} value={p.id}>{p.title}</option>
                ))}
              </select>
              <select
                value={repoAccountId}
                onChange={(e) => setRepoAccountId(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="">Select account...</option>
                {accs.map((a) => (
                  <option key={a.id} value={a.id}>{a.account_name} (@{a.github_username})</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddRepo(false)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createRepo.isPending}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
              >
                {createRepo.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        )}

        {loadingRepos ? (
          <div className="flex justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : rps.length === 0 ? (
          <p className="text-sm text-text-secondary text-center py-6">No repositories configured</p>
        ) : (
          <div className="space-y-2">
            {rps.map((repo) => (
              <div key={repo.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50">
                    <Globe className="h-4 w-4 text-violet-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text">{repo.repo_name}</p>
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                      <span className="flex items-center gap-1">
                        <Key className="h-2.5 w-2.5" /> Webhook configured
                      </span>
                      <span className={cn(
                        'flex items-center gap-1 font-medium',
                        repo.is_active ? 'text-emerald-600' : 'text-gray-400'
                      )}>
                        <Check className="h-2.5 w-2.5" />
                        {repo.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => deleteRepo.mutate(repo.id)}
                  disabled={deleteRepo.isPending}
                  className="text-text-secondary hover:text-danger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Webhook URL Display */}
        <div className="mt-4 rounded-lg border border-dashed border-border bg-surface-alt p-3">
          <p className="text-xs font-medium text-text-secondary mb-1">Webhook URL (paste in GitHub)</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs text-primary bg-white px-2 py-1 rounded border border-border overflow-x-auto">
              {window.location.origin}/api/git/webhook
            </code>
            <button
              onClick={handleCopyWebhook}
              className="rounded-lg p-1.5 text-text-secondary hover:bg-white transition-colors"
              title="Copy webhook URL"
            >
              {copied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

const OLLAMA_CLOUD_ENDPOINT = 'https://ollama.com/api'

const AI_MODEL_PRESETS: {
  id: string
  provider: string
  icon: string
  label: string
  cloudNote?: string
  models: { name: string; model_id: string; description: string; endpoint?: string }[]
}[] = [
  {
    id: 'ollama-local',
    provider: 'ollama',
    icon: '🦙',
    label: 'Ollama (Local)',
    models: [
      { name: 'Llama 3.2', model_id: 'llama3.2', description: 'Meta · 3B · Fast local inference' },
      { name: 'Llama 3.1', model_id: 'llama3.1', description: 'Meta · 8B · General purpose' },
      { name: 'Mistral 7B', model_id: 'mistral', description: 'Mistral AI · 7B · Balanced' },
      { name: 'Gemma 2', model_id: 'gemma2', description: 'Google · 9B · Efficient' },
      { name: 'Qwen 2.5', model_id: 'qwen2.5', description: 'Alibaba · 7B · Multilingual' },
      { name: 'DeepSeek R1', model_id: 'deepseek-r1', description: 'DeepSeek · 7B · Reasoning' },
    ],
  },
  {
    id: 'ollama-cloud',
    provider: 'ollama',
    icon: '☁️',
    label: 'Ollama Cloud',
    cloudNote: `Requires Ollama cloud endpoint. Update the endpoint_url after adding if your setup differs.`,
    models: [
      { name: 'GPT-OSS 120B', model_id: 'gpt-oss:120b-cloud', description: 'Large open-source model', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'GPT-OSS 20B', model_id: 'gpt-oss:20b-cloud', description: 'Medium open-source model', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'DeepSeek V3.1', model_id: 'deepseek-v3.1:671b-cloud', description: 'DeepSeek · 671B · Powerful reasoning', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'Qwen3 Coder', model_id: 'qwen3-coder:480b-cloud', description: 'Alibaba · Specialized for code', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'Qwen3 VL', model_id: 'qwen3-vl:235b-cloud', description: 'Alibaba · Vision & language', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'MiniMax M2', model_id: 'minimax-m2:cloud', description: 'Efficient high-performance model', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'ALM 4.6', model_id: 'alm-4.6:cloud', description: 'Advanced language model', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'Kimi K2.5', model_id: 'kimi-k2.5:cloud', description: 'Moonshot · Long context · Powerful', endpoint: OLLAMA_CLOUD_ENDPOINT },
    ],
  },
  {
    id: 'openai',
    provider: 'openai',
    icon: '⚡',
    label: 'OpenAI',
    models: [
      { name: 'GPT-4o', model_id: 'gpt-4o', description: 'Latest flagship · Multimodal' },
      { name: 'GPT-4o Mini', model_id: 'gpt-4o-mini', description: 'Fast & affordable' },
      { name: 'GPT-4 Turbo', model_id: 'gpt-4-turbo', description: 'High capability · 128K context' },
      { name: 'GPT-3.5 Turbo', model_id: 'gpt-3.5-turbo', description: 'Fast & cost-effective' },
    ],
  },
  {
    id: 'anthropic',
    provider: 'anthropic',
    icon: '🤖',
    label: 'Anthropic',
    models: [
      { name: 'Claude Opus 4.5', model_id: 'claude-opus-4-5-20251101', description: 'Most powerful · Complex tasks' },
      { name: 'Claude Sonnet 4.5', model_id: 'claude-sonnet-4-5-20251022', description: 'Balanced performance' },
      { name: 'Claude 3 Haiku', model_id: 'claude-3-haiku-20240307', description: 'Fastest · Lightweight tasks' },
    ],
  },
  {
    id: 'kimi',
    provider: 'kimi',
    icon: '🌙',
    label: 'Kimi (Moonshot)',
    models: [
      { name: 'Kimi K2.5', model_id: 'kimi-k2-5', description: 'Moonshot · Long context · Chinese/English' },
      { name: 'Moonshot v1 8K', model_id: 'moonshot-v1-8k', description: 'Moonshot · 8K context' },
      { name: 'Moonshot v1 32K', model_id: 'moonshot-v1-32k', description: 'Moonshot · 32K context' },
    ],
  },
]

function AIModelSettings() {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const [showAdd, setShowAdd] = useState(false)
  const [activeProvider, setActiveProvider] = useState('ollama-local')
  const [customMode, setCustomMode] = useState(false)
  const [modelName, setModelName] = useState('')
  const [provider, setProvider] = useState('ollama')
  const [modelId, setModelId] = useState('')
  const [endpointUrl, setEndpointUrl] = useState('')
  const [reindexStatus, setReindexStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [reindexResult, setReindexResult] = useState<number | null>(null)

  const { data: models, isLoading } = useQuery({
    queryKey: ['ai-models', ws?.id],
    queryFn: () => ws ? api.get<AIModel[]>(`${wsPath}/ai/models`) : api.get<AIModel[]>('/ai/models'),
  })

  const createModel = useMutation({
    mutationFn: (data: { name: string; provider: string; model_id: string; endpoint_url: string | null }) =>
      ws ? api.post(`${wsPath}/ai/models`, data) : api.post('/ai/models', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setShowAdd(false)
      setCustomMode(false)
      setModelName('')
      setProvider('ollama')
      setModelId('')
      setEndpointUrl('')
    },
  })

  const toggleModel = useMutation({
    mutationFn: (id: string) => ws ? api.put(`${wsPath}/ai/models/${id}/toggle`, {}) : api.put(`/ai/models/${id}/toggle`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-models'] }),
  })

  const deleteModel = useMutation({
    mutationFn: (id: string) => ws ? api.delete(`${wsPath}/ai/models/${id}`) : api.delete(`/ai/models/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-models'] }),
  })

  const list = models || []

  const { data: capabilities } = useQuery({
    queryKey: ['ai-capabilities', ws?.id],
    queryFn: () => api.get<{ has_project: boolean; can_execute_tools: boolean; indexed_documents: number }>(`${wsPath}/ai/chat/capabilities`),
    enabled: !!ws,
  })

  const reindexMutation = useMutation({
    mutationFn: () => api.post<{ total_indexed: number }>(`${wsPath}/ai/reindex`, {}),
    onSuccess: (data) => {
      setReindexStatus('done')
      setReindexResult(data.total_indexed)
      queryClient.invalidateQueries({ queryKey: ['ai-capabilities'] })
    },
    onError: () => setReindexStatus('error'),
  })

  const providerIcons: Record<string, string> = {
    ollama: '🦙',
    anthropic: '🤖',
    openai: '⚡',
    kimi: '🌙',
    custom: '🔧',
  }

  const activePreset = AI_MODEL_PRESETS.find((p) => p.id === activeProvider)
  const addedModelIds = new Set(list.map((m) => m.model_id))

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">AI Models for Commit Analysis</h2>
          <button
            onClick={() => { setShowAdd(!showAdd); setCustomMode(false) }}
            className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark"
          >
            <Plus className="h-3.5 w-3.5" /> Add Model
          </button>
        </div>

        {showAdd && (
          <div className="mb-4 rounded-lg border border-border bg-surface-alt overflow-hidden">
            {/* Provider tabs */}
            <div className="flex border-b border-border overflow-x-auto">
              {AI_MODEL_PRESETS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => { setActiveProvider(p.id); setCustomMode(false) }}
                  className={cn(
                    'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px',
                    activeProvider === p.id && !customMode
                      ? 'border-primary text-primary bg-white'
                      : 'border-transparent text-text-secondary hover:text-text'
                  )}
                >
                  <span>{p.icon}</span> {p.label}
                </button>
              ))}
              <button
                onClick={() => { setCustomMode(true); setProvider('custom') }}
                className={cn(
                  'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px',
                  customMode
                    ? 'border-primary text-primary bg-white'
                    : 'border-transparent text-text-secondary hover:text-text'
                )}
              >
                <span>🔧</span> Custom
              </button>
            </div>

            {/* Model list or custom form */}
            {!customMode ? (
              <div className="p-3 space-y-1.5">
                {activePreset?.cloudNote && (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-1">
                    ⚠️ {activePreset.cloudNote}
                  </p>
                )}
                {activePreset?.models.map((m) => {
                  const alreadyAdded = addedModelIds.has(m.model_id)
                  return (
                    <div
                      key={m.model_id}
                      className="flex items-center justify-between rounded-lg border border-border bg-white px-3 py-2.5 hover:border-primary/40 hover:bg-primary/5 transition-colors"
                    >
                      <div>
                        <p className="text-sm font-medium text-text">{m.name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="font-mono text-[11px] bg-surface-alt px-1.5 py-0.5 rounded text-text-secondary">
                            {m.model_id}
                          </span>
                          <span className="text-xs text-text-secondary">{m.description}</span>
                        </div>
                      </div>
                      <button
                        disabled={alreadyAdded || createModel.isPending}
                        onClick={() =>
                          createModel.mutate({
                            name: m.name,
                            provider: activeProvider,
                            model_id: m.model_id,
                            endpoint_url: m.endpoint ?? null,
                          })
                        }
                        className={cn(
                          'ml-3 shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                          alreadyAdded
                            ? 'bg-emerald-50 text-emerald-600 cursor-default'
                            : 'bg-primary text-white hover:bg-primary-dark disabled:opacity-50'
                        )}
                      >
                        {alreadyAdded ? <span className="flex items-center gap-1"><Check className="h-3 w-3" /> Added</span> : 'Add'}
                      </button>
                    </div>
                  )
                })}
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  createModel.mutate({ name: modelName, provider, model_id: modelId, endpoint_url: endpointUrl || null })
                }}
                className="p-4 space-y-3"
              >
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Display Name</label>
                    <input
                      placeholder="e.g. My GPT-4o"
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      required
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Provider</label>
                    <select
                      value={provider}
                      onChange={(e) => setProvider(e.target.value)}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
                    >
                      <option value="ollama">Ollama (Local)</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="openai">OpenAI</option>
                      <option value="kimi">Kimi</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Model ID</label>
                    <input
                      placeholder="e.g. gpt-4o"
                      value={modelId}
                      onChange={(e) => setModelId(e.target.value)}
                      required
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Endpoint URL <span className="text-text-secondary/60">(optional)</span></label>
                    <input
                      placeholder="https://..."
                      value={endpointUrl}
                      onChange={(e) => setEndpointUrl(e.target.value)}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => { setShowAdd(false); setCustomMode(false) }}
                    className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createModel.isPending}
                    className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                  >
                    {createModel.isPending ? 'Adding...' : 'Add Model'}
                  </button>
                </div>
              </form>
            )}

            {/* Close bar */}
            <div className="flex justify-end border-t border-border px-3 py-2">
              <button
                onClick={() => { setShowAdd(false); setCustomMode(false) }}
                className="text-xs text-text-secondary hover:text-text"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : list.length === 0 ? (
          <p className="text-sm text-text-secondary text-center py-6">No AI models configured</p>
        ) : (
          <div className="space-y-2">
            {list.map((model) => (
              <div
                key={model.id}
                className={cn(
                  'flex items-center justify-between rounded-lg border p-4 transition-colors',
                  model.is_active ? 'border-primary/30 bg-primary/5' : 'border-border'
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">{providerIcons[model.provider] || '🤖'}</span>
                  <div>
                    <p className="text-sm font-semibold text-text">{model.name}</p>
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                      <span className="uppercase tracking-wider font-medium">{model.provider}</span>
                      <span className="font-mono bg-surface-alt px-1.5 py-0.5 rounded text-[10px]">
                        {model.model_id}
                      </span>
                    </div>
                    {model.endpoint_url && (
                      <p className="text-[10px] text-text-secondary/60 mt-0.5 font-mono">
                        {model.endpoint_url}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => deleteModel.mutate(model.id)}
                    className="rounded-lg p-1.5 text-text-secondary hover:text-danger hover:bg-red-50 transition-colors"
                    title="Delete model"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => toggleModel.mutate(model.id)}
                    disabled={toggleModel.isPending}
                    className={cn(
                      'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                      model.is_active
                        ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                    )}
                  >
                    {model.is_active ? 'Active' : 'Disabled'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* RAG / Knowledge Base Section */}
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-text mb-1">AI Knowledge Base (RAG)</h2>
        <p className="text-xs text-text-secondary mb-4">
          The AI assistant uses vector embeddings of your workspace data to provide accurate answers.
          Re-index if data appears stale or after bulk imports.
        </p>

        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-alt p-4">
          <div>
            <p className="text-sm font-medium text-text">Indexed Documents</p>
            <p className="text-2xl font-bold text-primary mt-0.5">
              {capabilities?.indexed_documents ?? '—'}
            </p>
          </div>
          <button
            onClick={() => {
              setReindexStatus('running')
              reindexMutation.mutate()
            }}
            disabled={reindexStatus === 'running'}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50 flex items-center gap-2"
          >
            {reindexStatus === 'running' && <Loader2 className="h-4 w-4 animate-spin" />}
            {reindexStatus === 'running' ? 'Re-indexing…' : 'Re-index All Data'}
          </button>
        </div>

        {reindexStatus === 'done' && reindexResult !== null && (
          <p className="mt-3 text-sm text-emerald-600 font-medium">
            Re-indexing complete — {reindexResult} documents indexed.
          </p>
        )}
        {reindexStatus === 'error' && (
          <p className="mt-3 text-sm text-red-600 font-medium">
            Re-indexing failed. Please try again or check server logs.
          </p>
        )}
      </div>
    </div>
  )
}
