import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { GitAccount, RepoConfig, AIModel } from '@/types'
import {
  GitFork,
  Plus,
  Trash2,
  Check,
  X,
  Cpu,
  Globe,
  Key,
  RefreshCw,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const DEMO_ACCOUNTS: GitAccount[] = [
  { id: '1', account_name: 'Personal', github_username: 'cvrvai', created_at: '2026-04-01T00:00:00Z' },
]

const DEMO_REPOS: RepoConfig[] = [
  { id: '1', repo_name: 'cvrvai/oppm-ai', project_id: '1', github_account_id: '1', webhook_secret: '••••••', is_active: true },
]

const DEMO_MODELS: AIModel[] = [
  { id: '1', name: 'Kimi K2.5', provider: 'kimi', model_id: 'kimi-k2.5:cloud', is_active: true, endpoint_url: null },
  { id: '2', name: 'CodeLlama (Ollama)', provider: 'ollama', model_id: 'codellama:latest', is_active: true, endpoint_url: 'http://localhost:11434' },
  { id: '3', name: 'Claude Sonnet', provider: 'anthropic', model_id: 'claude-sonnet-4-20250514', is_active: false, endpoint_url: null },
]

export function Settings() {
  const [activeTab, setActiveTab] = useState<'github' | 'ai'>('github')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Settings</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          Configure GitHub integration and AI models
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {[
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

      {activeTab === 'github' ? <GitHubSettings /> : <AIModelSettings />}
    </div>
  )
}

function GitHubSettings() {
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [showAddRepo, setShowAddRepo] = useState(false)

  const { data: accounts } = useQuery({
    queryKey: ['github-accounts'],
    queryFn: () => api.get<GitAccount[]>('/github-accounts'),
    placeholderData: DEMO_ACCOUNTS,
  })

  const { data: repos } = useQuery({
    queryKey: ['repo-configs'],
    queryFn: () => api.get<RepoConfig[]>('/git/repo-map'),
    placeholderData: DEMO_REPOS,
  })

  const accs = accounts || DEMO_ACCOUNTS
  const rps = repos || DEMO_REPOS

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
          <div className="mb-4 rounded-lg border border-border bg-surface-alt p-4 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <input placeholder="Account name" className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
              <input placeholder="GitHub username" className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
              <input placeholder="Personal Access Token" type="password" className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowAddAccount(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white">Cancel</button>
              <button className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark">Save</button>
            </div>
          </div>
        )}

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
              <button className="text-text-secondary hover:text-danger">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
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
              <button className="text-text-secondary hover:text-danger">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>

        {/* Webhook URL Display */}
        <div className="mt-4 rounded-lg border border-dashed border-border bg-surface-alt p-3">
          <p className="text-xs font-medium text-text-secondary mb-1">Webhook URL (paste in GitHub)</p>
          <code className="text-xs text-primary bg-white px-2 py-1 rounded border border-border block overflow-x-auto">
            https://your-domain.com/api/git/webhook
          </code>
        </div>
      </div>
    </div>
  )
}

function AIModelSettings() {
  const { data: models } = useQuery({
    queryKey: ['ai-models'],
    queryFn: () => api.get<AIModel[]>('/ai/models'),
    placeholderData: DEMO_MODELS,
  })

  const list = models || DEMO_MODELS

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
          <button className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark">
            <Plus className="h-3.5 w-3.5" /> Add Model
          </button>
        </div>

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
                <button className="rounded-lg p-1.5 text-text-secondary hover:bg-surface-alt">
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
                <button
                  className={cn(
                    'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                    model.is_active
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  )}
                >
                  {model.is_active ? 'Active' : 'Disabled'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
