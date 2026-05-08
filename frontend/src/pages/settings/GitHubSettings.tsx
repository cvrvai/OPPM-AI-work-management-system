import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { GitAccount, PaginatedResponse, Project, RepoConfig } from '@/types'
import {
  GitFork,
  Plus,
  Trash2,
  Check,
  Globe,
  Key,
  Loader2,
  Copy,
  CheckCircle2,
  Pencil,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function GitHubSettings() {
  const queryClient = useQueryClient()
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [showAddRepo, setShowAddRepo] = useState(false)
  const [editingRepoId, setEditingRepoId] = useState<string | null>(null)
  const [editRepoName, setEditRepoName] = useState('')
  const [editRepoProjectId, setEditRepoProjectId] = useState('')
  const [editRepoAccountId, setEditRepoAccountId] = useState('')
  const [editWebhookSecret, setEditWebhookSecret] = useState('')
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
      const res = await api.get<PaginatedResponse<Project>>(`${wsPath}/projects`)
      return res.items ?? []
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

  const updateRepo = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.patch(`${wsPath}/git/repos/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repo-configs'] })
      setEditingRepoId(null)
    },
  })

  const accs = accounts || []
  const rps = repos || []

  const webhookBaseUrl = import.meta.env.VITE_WEBHOOK_BASE_URL?.replace(/\/$/, '') || window.location.origin
  const webhookUrl = `${webhookBaseUrl}/api/v1/git/webhook`

  const handleCopyWebhook = () => {
    navigator.clipboard.writeText(webhookUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
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
              <input placeholder="Account name" value={accountName} onChange={(e) => setAccountName(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
              <input placeholder="GitHub username" value={githubUsername} onChange={(e) => setGithubUsername(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
              <input placeholder="Personal Access Token" type="password" value={token} onChange={(e) => setToken(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowAddAccount(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white">Cancel</button>
              <button type="submit" disabled={createAccount.isPending} className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">{createAccount.isPending ? 'Saving...' : 'Save'}</button>
            </div>
          </form>
        )}

        {loadingAccounts ? (
          <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
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
                <button onClick={() => deleteAccount.mutate(acc.id)} disabled={deleteAccount.isPending} className="text-text-secondary hover:text-danger"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text">Repository Configurations</h2>
          <button onClick={() => setShowAddRepo(!showAddRepo)} className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark">
            <Plus className="h-3.5 w-3.5" /> Add Repo
          </button>
        </div>

        {showAddRepo && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              createRepo.mutate({ repo_name: repoName, project_id: repoProjectId, github_account_id: repoAccountId, webhook_secret: webhookSecret })
            }}
            className="mb-4 rounded-lg border border-border bg-surface-alt p-4 space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="owner/repo-name" value={repoName} onChange={(e) => setRepoName(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
              <input placeholder="Webhook Secret (min 8 chars)" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} required minLength={8} className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
              <select value={repoProjectId} onChange={(e) => setRepoProjectId(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary">
                <option value="">Select project...</option>
                {(projects || []).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
              <select value={repoAccountId} onChange={(e) => setRepoAccountId(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary">
                <option value="">Select account...</option>
                {accs.map((a) => <option key={a.id} value={a.id}>{a.account_name} (@{a.github_username})</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowAddRepo(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white">Cancel</button>
              <button type="submit" disabled={createRepo.isPending} className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">{createRepo.isPending ? 'Saving...' : 'Save'}</button>
            </div>
          </form>
        )}

        {loadingRepos ? (
          <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
        ) : rps.length === 0 ? (
          <p className="text-sm text-text-secondary text-center py-6">No repositories configured</p>
        ) : (
          <div className="space-y-2">
            {rps.map((repo) => (
              <div key={repo.id} className="rounded-lg border border-border">
                <div className="flex items-center justify-between p-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50"><Globe className="h-4 w-4 text-violet-600" /></div>
                    <div>
                      <p className="text-sm font-medium text-text">{repo.repo_name}</p>
                      <div className="flex items-center gap-2 text-xs text-text-secondary">
                        {projects.find(p => p.id === repo.project_id) && (
                          <span className="font-medium text-violet-600">{projects.find(p => p.id === repo.project_id)!.title}</span>
                        )}
                        <span className="flex items-center gap-1"><Key className="h-2.5 w-2.5" /> Webhook configured</span>
                        <span className={cn('flex items-center gap-1 font-medium', repo.is_active ? 'text-emerald-600' : 'text-gray-400')}>
                          <Check className="h-2.5 w-2.5" />{repo.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        if (editingRepoId === repo.id) {
                          setEditingRepoId(null)
                        } else {
                          setEditingRepoId(repo.id)
                          setEditRepoName(repo.repo_name)
                          setEditRepoProjectId(repo.project_id)
                          setEditRepoAccountId(repo.github_account_id ?? '')
                          setEditWebhookSecret('')
                        }
                      }}
                      className={cn('rounded p-1 transition-colors', editingRepoId === repo.id ? 'text-primary bg-primary/10' : 'text-text-secondary hover:text-primary')}
                      title="Edit"
                    >
                      {editingRepoId === repo.id ? <X className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
                    </button>
                    <button onClick={() => deleteRepo.mutate(repo.id)} disabled={deleteRepo.isPending} className="rounded p-1 text-text-secondary hover:text-danger" title="Delete"><Trash2 className="h-4 w-4" /></button>
                  </div>
                </div>

                {editingRepoId === repo.id && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault()
                      const payload: Record<string, unknown> = { repo_name: editRepoName, project_id: editRepoProjectId, github_account_id: editRepoAccountId }
                      if (editWebhookSecret) payload.webhook_secret = editWebhookSecret
                      updateRepo.mutate({ id: repo.id, data: payload })
                    }}
                    className="border-t border-border bg-surface-alt px-3 pb-3 pt-3 space-y-3"
                  >
                    <div className="grid grid-cols-2 gap-3">
                      <input placeholder="owner/repo-name" value={editRepoName} onChange={(e) => setEditRepoName(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                      <input placeholder="New webhook secret (leave blank to keep current)" value={editWebhookSecret} onChange={(e) => setEditWebhookSecret(e.target.value)} minLength={editWebhookSecret ? 8 : undefined} className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                      <select value={editRepoProjectId} onChange={(e) => setEditRepoProjectId(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary">
                        <option value="">Select project...</option>
                        {(projects || []).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                      </select>
                      <select value={editRepoAccountId} onChange={(e) => setEditRepoAccountId(e.target.value)} required className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary">
                        <option value="">Select account...</option>
                        {accs.map((a) => <option key={a.id} value={a.id}>{a.account_name} (@{a.github_username})</option>)}
                      </select>
                    </div>
                    <div className="flex justify-end gap-2">
                      <button type="button" onClick={() => setEditingRepoId(null)} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white">Cancel</button>
                      <button type="submit" disabled={updateRepo.isPending} className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">{updateRepo.isPending ? 'Saving...' : 'Save changes'}</button>
                    </div>
                  </form>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 rounded-lg border border-dashed border-border bg-surface-alt p-3">
          <p className="text-xs font-medium text-text-secondary mb-1">Webhook URL (paste in GitHub)</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs text-primary bg-white px-2 py-1 rounded border border-border overflow-x-auto">{webhookUrl}</code>
            <button onClick={handleCopyWebhook} className="rounded-lg p-1.5 text-text-secondary hover:bg-white transition-colors" title="Copy webhook URL">
              {copied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
