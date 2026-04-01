import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { api } from '@/lib/api'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'

type AcceptResult = { workspace_id: string; workspace_name: string }

export function AcceptInvite() {
  const { token } = useParams<{ token: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { session, loading: authLoading } = useAuthStore()
  const { fetchWorkspaces, setCurrentWorkspace } = useWorkspaceStore()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const [wsName, setWsName] = useState('')

  useEffect(() => {
    if (authLoading) return

    if (!session) {
      navigate(`/login?redirect=/invites/${token}`, { replace: true })
      return
    }

    if (!token) {
      setStatus('error')
      setMessage('Invalid invite link')
      return
    }

    api.post<AcceptResult>('/v1/invites/accept', { token })
      .then(async (result) => {
        setStatus('success')
        setWsName(result.workspace_name)
        // Refresh workspaces and select the new one
        await fetchWorkspaces()
        const ws = useWorkspaceStore.getState().workspaces.find(w => w.id === result.workspace_id)
        if (ws) setCurrentWorkspace(ws)
      })
      .catch((err: Error) => {
        setStatus('error')
        setMessage(err.message || 'Failed to accept invite')
      })
  }, [session, authLoading, token, navigate, fetchWorkspaces, setCurrentWorkspace])

  if (authLoading || status === 'loading') {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-secondary">Accepting invitation...</p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4">
        <CheckCircle className="h-12 w-12 text-green-500" />
        <h2 className="text-xl font-semibold">Welcome to {wsName}!</h2>
        <p className="text-secondary">You've successfully joined the workspace.</p>
        <button
          onClick={() => navigate('/', { replace: true })}
          className="mt-4 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          Go to Dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4">
      <XCircle className="h-12 w-12 text-danger" />
      <h2 className="text-xl font-semibold">Invitation Failed</h2>
      <p className="text-secondary">{message}</p>
      <button
        onClick={() => navigate('/', { replace: true })}
        className="mt-4 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
      >
        Go to Dashboard
      </button>
    </div>
  )
}
