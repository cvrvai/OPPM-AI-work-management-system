import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { GitAccount, RepoConfig, AIModel, Project } from '@/types'
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
} from 'lucide-react'
import { cn, getInitials } from '@/lib/utils'

export function Settings() {
  const [activeTab, setActiveTab] = useState<'profile' | 'github' | 'ai'>('profile')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Settings</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          Configure your profile, GitHub integration, and AI models
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {[
          { id: 'profile' as const, label: 'Profile', icon: UserCircle },
          { id: 'github' as const, label: 'GitHub Integration', icon: GitFork },
          { id: 'ai' as const, label: 'AI Models', icon: Cpu },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors -mb-px',
              activeTab === id
                ? 'border-primary text-primary'
                : 'border-transparent text-text-secondary hover:text-text'
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && <ProfileSettings />}
      {activeTab === 'github' && <GitHubSettings />}
      {activeTab === 'ai' && <AIModelSettings />}
    </div>
  )
}

function ProfileSettings() {
  const user = useAuthStore((s) => s.user)
  const email = user?.email || ''
  const name = user?.user_metadata?.full_name || email.split('@')[0]
  const [displayName, setDisplayName] = useState(name)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const { supabase } = await import('@/lib/supabase')
      await supabase.auth.updateUser({
        data: { full_name: displayName },
      })
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
    queryFn: () => ws ? api.get<GitAccount[]>(`${wsPath}/github-accounts`) : api.get<GitAccount[]>('/github-accounts'),
  })

  const { data: repos, isLoading: loadingRepos } = useQuery({
    queryKey: ['repo-configs', ws?.id],
    queryFn: () => ws ? api.get<RepoConfig[]>(`${wsPath}/git/repos`) : api.get<RepoConfig[]>('/git/repo-map'),
  })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      if (ws) {
        const res = await api.get<{ data: Project[] }>(`${wsPath}/projects`)
        return (res as any)?.data ?? res as unknown as Project[]
      }
      return api.get<Project[]>('/projects')
    },
  })

  const createAccount = useMutation({
    mutationFn: (data: { account_name: string; github_username: string; token: string }) =>
      ws ? api.post(`${wsPath}/github-accounts`, data) : api.post('/github-accounts', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-accounts'] })
      setShowAddAccount(false)
      setAccountName('')
      setGithubUsername('')
      setToken('')
    },
  })

  const deleteAccount = useMutation({
    mutationFn: (id: string) => ws ? api.delete(`${wsPath}/github-accounts/${id}`) : api.delete(`/github-accounts/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['github-accounts'] }),
  })

  const createRepo = useMutation({
    mutationFn: (data: { repo_name: string; project_id: string; github_account_id: string; webhook_secret: string }) =>
      ws ? api.post(`${wsPath}/git/repos`, data) : api.post('/git/repo-map', data),
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
    mutationFn: (id: string) => ws ? api.delete(`${wsPath}/git/repos/${id}`) : api.delete(`/git/repo-map/${id}`),
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

function AIModelSettings() {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const [showAdd, setShowAdd] = useState(false)
  const [modelName, setModelName] = useState('')
  const [provider, setProvider] = useState('ollama')
  const [modelId, setModelId] = useState('')
  const [endpointUrl, setEndpointUrl] = useState('')

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

  const providerIcons: Record<string, string> = {
    ollama: '🦙',
    anthropic: '🤖',
    openai: '⚡',
    kimi: '🌙',
    custom: '🔧',
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">AI Models for Commit Analysis</h2>
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark"
          >
            <Plus className="h-3.5 w-3.5" /> Add Model
          </button>
        </div>

        {showAdd && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              createModel.mutate({
                name: modelName,
                provider,
                model_id: modelId,
                endpoint_url: endpointUrl || null,
              })
            }}
            className="mb-4 rounded-lg border border-border bg-surface-alt p-4 space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <input
                placeholder="Model name (e.g. GPT-4o)"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="ollama">Ollama (Local)</option>
                <option value="anthropic">Anthropic</option>
                <option value="openai">OpenAI</option>
                <option value="kimi">Kimi</option>
                <option value="custom">Custom</option>
              </select>
              <input
                placeholder="Model ID (e.g. gpt-4o)"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                required
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                placeholder="Endpoint URL (optional)"
                value={endpointUrl}
                onChange={(e) => setEndpointUrl(e.target.value)}
                className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAdd(false)}
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
    </div>
  )
}
