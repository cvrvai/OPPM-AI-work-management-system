import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { api } from '@/lib/api'
import { CheckCircle, XCircle, Loader2, Users, Shield, Eye, Crown, LogIn } from 'lucide-react'
import { cn, getInitials } from '@/lib/utils'
import type { WorkspaceRole } from '@/types'

type InvitePreview = {
  invite_id: string
  workspace_id: string
  workspace_name: string
  workspace_slug: string
  inviter_name: string
  role: WorkspaceRole
  expires_at: string
  accepted_at: string | null
  member_count: number
  is_expired: boolean
  is_accepted: boolean
}

type AcceptResult = { workspace_id: string; workspace_name: string }

const ROLE_CONFIG: Record<WorkspaceRole, { label: string; color: string; icon: typeof Crown; description: string }> = {
  owner:  { label: 'Owner',  color: 'bg-amber-100 text-amber-700',  icon: Crown,  description: 'Full control' },
  admin:  { label: 'Admin',  color: 'bg-purple-100 text-purple-700', icon: Shield, description: 'Manage members & settings' },
  member: { label: 'Member', color: 'bg-blue-100 text-blue-700',    icon: Users,  description: 'Create projects and tasks' },
  viewer: { label: 'Viewer', color: 'bg-gray-100 text-gray-600',    icon: Eye,    description: 'Read-only access' },
}

function getInviteErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : 'Unable to process this invitation right now.'
  const normalized = message.toLowerCase()

  if (normalized.includes('expired')) {
    return 'This invitation has expired. Ask a workspace admin to resend it.'
  }
  if (normalized.includes('workspace not found') || normalized.includes('not found')) {
    return 'This workspace is no longer available. Ask the inviter to send a fresh link.'
  }
  if (normalized.includes('already') || normalized.includes('member')) {
    return 'You already belong to this workspace. You can go straight to your dashboard.'
  }

  return message
}

export function AcceptInvite() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { isAuthenticated: session, loading: authLoading } = useAuthStore()
  const { fetchWorkspaces, setCurrentWorkspace } = useWorkspaceStore()

  const [preview, setPreview] = useState<InvitePreview | null>(null)
  const [previewError, setPreviewError] = useState('')
  const [accepting, setAccepting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [acceptError, setAcceptError] = useState('')

  // Always fetch the invite preview first (public — no auth needed)
  useEffect(() => {
    if (!token) {
      setPreviewError('Invalid invite link')
      return
    }
    api.get<InvitePreview>(`/v1/invites/preview/${token}`)
      .then(setPreview)
      .catch((err: unknown) => setPreviewError(getInviteErrorMessage(err)))
  }, [token])

  const handleAccept = async () => {
    if (!token || !session) return
    setAccepting(true)
    setAcceptError('')
    try {
      const result = await api.post<AcceptResult>('/v1/invites/accept', { token })
      setAccepted(true)
      await fetchWorkspaces()
      const ws = useWorkspaceStore.getState().workspaces.find(w => w.id === result.workspace_id)
      if (ws) setCurrentWorkspace(ws)
      setTimeout(() => navigate('/', { replace: true }), 1500)
    } catch (err) {
      setAcceptError(getInviteErrorMessage(err))
    } finally {
      setAccepting(false)
    }
  }

  const handleDecline = () => {
    navigate(session ? '/' : '/login', { replace: true })
  }

  // Loading state — waiting for preview
  if (!preview && !previewError) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-text-secondary">Loading invitation...</p>
      </div>
    )
  }

  // Error state
  if (previewError) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 px-4">
        <XCircle className="h-12 w-12 text-danger" />
        <h2 className="text-xl font-semibold text-text">Invitation Unavailable</h2>
        <p className="text-text-secondary text-sm">{previewError}</p>
        <button
          onClick={() => navigate(session ? '/' : '/login', { replace: true })}
          className="mt-2 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          {session ? 'Go to Dashboard' : 'Sign In'}
        </button>
      </div>
    )
  }

  // Expired
  if (preview!.is_expired) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 px-4">
        <XCircle className="h-12 w-12 text-danger" />
        <h2 className="text-xl font-semibold text-text">Invitation Expired</h2>
        <p className="text-sm text-text-secondary">
          This invitation to <strong>{preview!.workspace_name}</strong> has expired. Ask the admin to resend it.
        </p>
        <button
          onClick={() => navigate(session ? '/' : '/login', { replace: true })}
          className="mt-2 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          {session ? 'Go to Dashboard' : 'Sign In'}
        </button>
      </div>
    )
  }

  // Already accepted
  if (preview!.is_accepted) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 px-4">
        <CheckCircle className="h-12 w-12 text-emerald-500" />
        <h2 className="text-xl font-semibold text-text">Already Joined</h2>
        <p className="text-sm text-text-secondary">
          This invitation to <strong>{preview!.workspace_name}</strong> has already been used.
        </p>
        <button
          onClick={() => navigate('/', { replace: true })}
          className="mt-2 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          Go to Dashboard
        </button>
      </div>
    )
  }

  // Successfully joined
  if (accepted) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4">
        <CheckCircle className="h-12 w-12 text-emerald-500" />
        <h2 className="text-xl font-semibold text-text">Welcome to {preview!.workspace_name}!</h2>
        <p className="text-sm text-text-secondary">Redirecting you to the dashboard...</p>
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
      </div>
    )
  }

  const roleInfo = ROLE_CONFIG[preview!.role] || ROLE_CONFIG.member
  const RoleIcon = roleInfo.icon

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-alt p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-white text-xl font-bold shadow-sm">
            {getInitials(preview!.workspace_name)}
          </div>
          <h1 className="text-2xl font-bold text-text">You're Invited!</h1>
          <p className="mt-1 text-sm text-text-secondary">
            <strong>{preview!.inviter_name}</strong> invited you to join a workspace
          </p>
        </div>

        {/* Workspace card */}
        <div className="rounded-xl border border-border bg-white p-6 shadow-sm space-y-4">
          {/* Workspace info */}
          <div className="flex items-center gap-4 pb-4 border-b border-border">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary text-lg font-bold">
              {getInitials(preview!.workspace_name)}
            </div>
            <div>
              <p className="font-semibold text-text text-lg">{preview!.workspace_name}</p>
              <p className="text-sm text-text-secondary flex items-center gap-1">
                <Users className="h-3.5 w-3.5" />
                {preview!.member_count} member{preview!.member_count !== 1 ? 's' : ''}
              </p>
            </div>
          </div>

          {/* Invite details */}
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">Your role</span>
              <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', roleInfo.color)}>
                <RoleIcon className="h-3 w-3" />
                {roleInfo.label}
              </span>
            </div>
            <div className="flex items-start justify-between">
              <span className="text-text-secondary">Access</span>
              <span className="text-text text-right max-w-[200px]">{roleInfo.description}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">Invited by</span>
              <span className="text-text">{preview!.inviter_name}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">Expires</span>
              <span className="text-text">
                {new Date(preview!.expires_at).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}
              </span>
            </div>
          </div>

          {/* Auth required notice */}
          {!authLoading && !session && (
            <div className="rounded-lg bg-primary/5 border border-primary/20 px-4 py-3 text-sm text-primary">
              <LogIn className="inline h-4 w-4 mr-1.5 -mt-0.5" />
              You need to <strong>sign in or create an account</strong> to accept this invitation.
            </div>
          )}

          {acceptError && (
            <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{acceptError}</p>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 pt-1">
            {!authLoading && !session ? (
              <button
                onClick={() => navigate(`/login?invite=${token}`, { replace: true })}
                className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
              >
                Sign In to Join
              </button>
            ) : (
              <button
                onClick={handleAccept}
                disabled={accepting || authLoading}
                className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50 transition-colors"
              >
                {accepting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : 'Join Workspace'}
              </button>
            )}
            <button
              onClick={handleDecline}
              className="flex-1 rounded-lg border border-border py-2.5 text-sm font-medium text-text hover:bg-surface-alt transition-colors"
            >
              Decline
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
