import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { api } from '@/lib/api'
import { Target } from 'lucide-react'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { signIn, signUp } = useAuthStore()
  const { fetchWorkspaces, setCurrentWorkspace } = useWorkspaceStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const inviteToken = searchParams.get('invite')

  // After auth, if there's an invite token, accept it then navigate
  const handlePostAuth = async () => {
    if (inviteToken) {
      try {
        const result = await api.post<{ workspace_id: string; workspace_name: string }>(
          '/v1/invites/accept',
          { token: inviteToken }
        )
        await fetchWorkspaces()
        const ws = useWorkspaceStore.getState().workspaces.find(w => w.id === result.workspace_id)
        if (ws) setCurrentWorkspace(ws)
        navigate('/', { replace: true })
      } catch {
        // Invite accept failed (e.g. already a member) — still navigate home
        navigate('/', { replace: true })
      }
    } else {
      navigate('/', { replace: true })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isSignUp) {
        await signUp(email, password)
        if (inviteToken) {
          // After signup, user can proceed to accept invite
          await handlePostAuth()
        } else {
          await handlePostAuth()
        }
      } else {
        await signIn(email, password)
        await handlePostAuth()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-alt">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary">
            <Target className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text">OPPM AI</h1>
          <p className="text-sm text-text-secondary mt-1">Work Management System</p>
        </div>

        {/* Invite context banner */}
        {inviteToken && (
          <div className="mb-4 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary text-center">
            Sign in or create an account to join the workspace you were invited to.
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-white p-6 shadow-sm space-y-4">
          <h2 className="text-lg font-semibold text-center">
            {isSignUp ? 'Create Account' : 'Sign In'}
          </h2>

          {error && (
            <div className={`rounded-lg px-3 py-2 text-sm ${error.includes('Check your email') ? 'bg-emerald-50 text-emerald-700' : 'bg-danger/10 text-danger'}`}>
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50 transition-colors"
          >
            {loading ? 'Please wait...' : isSignUp ? 'Sign Up' : 'Sign In'}
          </button>

          <p className="text-center text-sm text-text-secondary">
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              type="button"
              onClick={() => { setIsSignUp(!isSignUp); setError('') }}
              className="font-medium text-primary hover:underline"
            >
              {isSignUp ? 'Sign In' : 'Sign Up'}
            </button>
          </p>
        </form>
      </div>
    </div>
  )
}
