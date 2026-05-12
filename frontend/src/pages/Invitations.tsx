import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listMyInvitesRouteApiV1InvitesMyInvitesGet,
  acceptInviteRouteApiV1InvitesAcceptPost,
  declineInviteRouteApiV1InvitesInviteIdDeclinePost,
} from '@/generated/workspace-api/sdk.gen'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { MyInvite } from '@/types'
import { Building2, UserCheck, Clock, CheckCircle2, X, Inbox } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'

function roleBadgeClass(role: string) {
  switch (role) {
    case 'admin': return 'bg-violet-100 text-violet-700'
    case 'viewer': return 'bg-slate-100 text-slate-600'
    default: return 'bg-blue-100 text-blue-700'
  }
}

function timeRemaining(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now()
  if (diff <= 0) return 'Expired'
  const days = Math.floor(diff / 86_400_000)
  if (days > 0) return `${days}d remaining`
  const hours = Math.floor(diff / 3_600_000)
  return `${hours}h remaining`
}

export function Invitations() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces)
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace)
  const [accepted, setAccepted] = useState<Set<string>>(new Set())
  const [declined, setDeclined] = useState<Set<string>>(new Set())

  const { data: invites = [], isLoading } = useQuery({
    queryKey: ['my-invites'],
    queryFn: () =>
      listMyInvitesRouteApiV1InvitesMyInvitesGet({ client: workspaceClient }).then(
        (res) => (res.data ?? []) as MyInvite[]
      ),
    staleTime: 30_000,
  })

  const acceptMutation = useMutation({
    mutationFn: (invite: MyInvite) =>
      acceptInviteRouteApiV1InvitesAcceptPost({
        client: workspaceClient,
        body: { token: invite.token },
      }).then((res) => res.data as { workspace_id: string; workspace_name: string }),
    onSuccess: async (data, invite) => {
      setAccepted((prev) => new Set(prev).add(invite.id))
      qc.invalidateQueries({ queryKey: ['my-invites'] })
      // Refresh workspace list so the new workspace is available, then switch to it
      await fetchWorkspaces()
      const newWs = useWorkspaceStore.getState().workspaces.find((w) => w.id === data.workspace_id)
      if (newWs) {
        setCurrentWorkspace(newWs)
        navigate('/')
      }
    },
  })

  const declineMutation = useMutation({
    mutationFn: (inviteId: string) =>
      declineInviteRouteApiV1InvitesInviteIdDeclinePost({
        client: workspaceClient,
        path: { invite_id: inviteId },
      }).then((res) => res.data),
    onSuccess: (_data, inviteId) => {
      setDeclined((prev) => new Set(prev).add(inviteId))
      qc.invalidateQueries({ queryKey: ['my-invites'] })
    },
  })

  const visible = invites.filter((i) => !accepted.has(i.id) && !declined.has(i.id))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Invitations</h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            Workspace invitations sent to your account
          </p>
        </div>
        {!isLoading && visible.length > 0 && (
          <span className="mt-1 rounded-full bg-surface-alt px-3 py-1 text-xs font-medium text-text-secondary">
            {visible.length} pending
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg border border-border bg-white p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-4 w-64" />
                  <Skeleton className="h-4 w-32" />
                </div>
                <div className="flex gap-2">
                  <Skeleton className="h-9 w-20 rounded-md" />
                  <Skeleton className="h-9 w-20 rounded-md" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-white py-24 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 mb-4">
            <Inbox className="h-8 w-8 text-slate-400" />
          </div>
          <p className="text-base font-semibold text-text">No pending invitations</p>
          <p className="mt-1 max-w-xs text-sm text-text-secondary">
            When someone invites you to a workspace, it will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {visible.map((invite) => {
            const isAccepting = acceptMutation.isPending && acceptMutation.variables?.id === invite.id
            const isDeclining = declineMutation.isPending && declineMutation.variables === invite.id
            const expired = invite.is_expired

            return (
              <div
                key={invite.id}
                className={cn(
                  'rounded-lg border bg-white p-4 transition-opacity',
                  expired ? 'opacity-60 border-border' : 'border-border hover:border-primary/30'
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Workspace */}
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-surface-alt border border-border flex-shrink-0">
                        <Building2 className="h-4 w-4 text-text-secondary" />
                      </div>
                      <div>
                        <p className="font-semibold text-text">{invite.workspace_name}</p>
                        <p className="text-xs text-text-secondary">@{invite.workspace_slug}</p>
                      </div>
                    </div>

                    {/* Inviter + Role */}
                    <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
                      <UserCheck className="h-3.5 w-3.5 flex-shrink-0" />
                      <span>
                        Invited by{' '}
                        <span className="font-medium text-text">
                          {invite.inviter_name || 'a workspace admin'}
                        </span>
                      </span>
                      <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', roleBadgeClass(invite.role))}>
                        {invite.role}
                      </span>
                    </div>

                    {/* Expiry */}
                    <div className={cn('flex items-center gap-1.5 text-xs', expired ? 'text-red-500' : 'text-text-secondary')}>
                      <Clock className="h-3.5 w-3.5" />
                      {timeRemaining(invite.expires_at)}
                    </div>
                  </div>

                  {/* Actions */}
                  {!expired && (
                    <div className="flex flex-shrink-0 gap-2">
                      <button
                        onClick={() => declineMutation.mutate(invite.id)}
                        disabled={isDeclining || isAccepting}
                        className="flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-text-secondary hover:border-danger hover:text-danger transition-colors disabled:opacity-50"
                      >
                        <X className="h-3.5 w-3.5" />
                        Decline
                      </button>
                      <button
                        onClick={() => acceptMutation.mutate(invite)}
                        disabled={isAccepting || isDeclining}
                        className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {isAccepting ? 'Joining…' : 'Accept'}
                      </button>
                    </div>
                  )}
                </div>

                {/* Error feedback */}
                {acceptMutation.isError && acceptMutation.variables?.id === invite.id && (
                  <p className="mt-3 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
                    {(acceptMutation.error as Error).message}
                  </p>
                )}
                {declineMutation.isError && declineMutation.variables === invite.id && (
                  <p className="mt-3 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
                    {(declineMutation.error as Error).message}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
