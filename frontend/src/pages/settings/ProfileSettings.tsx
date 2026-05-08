import { useState } from 'react'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Loader2, CheckCircle2 } from 'lucide-react'
import { getInitials } from '@/lib/utils'

export function ProfileSettings() {
  const user = useAuthStore((s) => s.user)
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const email = user?.email || ''
  const name = user?.full_name || user?.user_metadata?.full_name || email.split('@')[0]
  const [displayName, setDisplayName] = useState(name)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.patch('/auth/profile', { full_name: displayName })
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
