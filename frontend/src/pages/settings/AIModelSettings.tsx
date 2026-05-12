import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { intelligenceClient } from '@/lib/api/intelligenceClient'
import {
  listAiModelsApiV1WorkspacesWorkspaceIdAiModelsGet,
  addAiModelApiV1WorkspacesWorkspaceIdAiModelsPost,
  toggleAiModelApiV1WorkspacesWorkspaceIdAiModelsModelIdTogglePut,
  deleteAiModelApiV1WorkspacesWorkspaceIdAiModelsModelIdDelete,
  capabilitiesRouteApiV1WorkspacesWorkspaceIdAiChatCapabilitiesGet,
  reindexRouteApiV1WorkspacesWorkspaceIdAiReindexPost,
} from '@/generated/intelligence-api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { AIModel } from '@/types'
import { Plus, Trash2, Check, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

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
      { name: 'Gemma 4 31B', model_id: 'gemma4:31b-cloud', description: 'Google · 31B · Strong general reasoning', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'DeepSeek V3.1', model_id: 'deepseek-v3.1:671b-cloud', description: 'DeepSeek · 671B · Powerful reasoning', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'Qwen3 Coder', model_id: 'qwen3-coder:480b-cloud', description: 'Alibaba · Specialized for code', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'Qwen3 VL', model_id: 'qwen3-vl:235b-cloud', description: 'Alibaba · Vision & language', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'MiniMax M2', model_id: 'minimax-m2:cloud', description: 'Efficient high-performance model', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'ALM 4.6', model_id: 'alm-4.6:cloud', description: 'Advanced language model', endpoint: OLLAMA_CLOUD_ENDPOINT },
      { name: 'Kimi K2.6', model_id: 'kimi-k2.6:cloud', description: 'Moonshot · Long context · Powerful', endpoint: OLLAMA_CLOUD_ENDPOINT },
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
      { name: 'Kimi K2.6', model_id: 'kimi-k2-5', description: 'Moonshot · Long context · Chinese/English' },
      { name: 'Moonshot v1 8K', model_id: 'moonshot-v1-8k', description: 'Moonshot · 8K context' },
      { name: 'Moonshot v1 32K', model_id: 'moonshot-v1-32k', description: 'Moonshot · 32K context' },
    ],
  },
]

export function AIModelSettings() {
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
    queryFn: async () => {
      if (!ws) return []
      const res = await listAiModelsApiV1WorkspacesWorkspaceIdAiModelsGet({
        client: intelligenceClient,
        path: { workspace_id: ws.id },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to load AI models')
      }
      return (res.data ?? []) as AIModel[]
    },
    enabled: !!ws,
  })

  const createModel = useMutation({
    mutationFn: async (data: { name: string; provider: string; model_id: string; endpoint_url: string | null }) => {
      if (!ws) throw new Error('Select a workspace before managing AI models.')
      const res = await addAiModelApiV1WorkspacesWorkspaceIdAiModelsPost({
        client: intelligenceClient,
        path: { workspace_id: ws.id },
        body: data,
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to add AI model')
      }
      return res.data
    },
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
    mutationFn: async (id: string) => {
      if (!ws) throw new Error('Select a workspace before managing AI models.')
      const res = await toggleAiModelApiV1WorkspacesWorkspaceIdAiModelsModelIdTogglePut({
        client: intelligenceClient,
        path: { workspace_id: ws.id, model_id: id },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to toggle AI model')
      }
      return res.data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-models'] }),
  })

  const deleteModel = useMutation({
    mutationFn: async (id: string) => {
      if (!ws) throw new Error('Select a workspace before managing AI models.')
      const res = await deleteAiModelApiV1WorkspacesWorkspaceIdAiModelsModelIdDelete({
        client: intelligenceClient,
        path: { workspace_id: ws.id, model_id: id },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to delete AI model')
      }
      return res.data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-models'] }),
  })

  const list = models || []

  const { data: capabilities } = useQuery({
    queryKey: ['ai-capabilities', ws?.id],
    queryFn: async () => {
      if (!ws) return null
      const res = await capabilitiesRouteApiV1WorkspacesWorkspaceIdAiChatCapabilitiesGet({
        client: intelligenceClient,
        path: { workspace_id: ws.id },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to load AI capabilities')
      }
      return res.data
    },
    enabled: !!ws,
  })

  const reindexMutation = useMutation({
    mutationFn: async () => {
      if (!ws) throw new Error('Select a workspace before reindexing.')
      const res = await reindexRouteApiV1WorkspacesWorkspaceIdAiReindexPost({
        client: intelligenceClient,
        path: { workspace_id: ws.id },
      })
      if (res.error) {
        throw new Error((res.error as { detail?: string })?.detail || 'Failed to reindex')
      }
      return res.data
    },
    onSuccess: (data) => {
      setReindexStatus('done')
      setReindexResult(data?.total_indexed ?? null)
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
          <button onClick={() => { setShowAdd(!showAdd); setCustomMode(false) }} className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary-dark">
            <Plus className="h-3.5 w-3.5" /> Add Model
          </button>
        </div>

        {showAdd && (
          <div className="mb-4 rounded-lg border border-border bg-surface-alt overflow-hidden">
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
                  customMode ? 'border-primary text-primary bg-white' : 'border-transparent text-text-secondary hover:text-text'
                )}
              >
                <span>🔧</span> Custom
              </button>
            </div>

            {!customMode ? (
              <div className="p-3 space-y-1.5">
                {activePreset?.cloudNote && (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-1">⚠️ {activePreset.cloudNote}</p>
                )}
                {activePreset?.models.map((m) => {
                  const alreadyAdded = addedModelIds.has(m.model_id)
                  return (
                    <div key={m.model_id} className="flex items-center justify-between rounded-lg border border-border bg-white px-3 py-2.5 hover:border-primary/40 hover:bg-primary/5 transition-colors">
                      <div>
                        <p className="text-sm font-medium text-text">{m.name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="font-mono text-[11px] bg-surface-alt px-1.5 py-0.5 rounded text-text-secondary">{m.model_id}</span>
                          <span className="text-xs text-text-secondary">{m.description}</span>
                        </div>
                      </div>
                      <button
                        disabled={alreadyAdded || createModel.isPending}
                        onClick={() =>
                          createModel.mutate({
                            name: m.name,
                            provider: activePreset?.provider ?? activeProvider,
                            model_id: m.model_id,
                            endpoint_url: m.endpoint ?? null,
                          })
                        }
                        className={cn(
                          'ml-3 shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                          alreadyAdded ? 'bg-emerald-50 text-emerald-600 cursor-default' : 'bg-primary text-white hover:bg-primary-dark disabled:opacity-50'
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
                    <input placeholder="e.g. My GPT-4o" value={modelName} onChange={(e) => setModelName(e.target.value)} required className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Provider</label>
                    <select value={provider} onChange={(e) => setProvider(e.target.value)} className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary">
                      <option value="ollama">Ollama (Local)</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="openai">OpenAI</option>
                      <option value="kimi">Kimi</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Model ID</label>
                    <input placeholder="e.g. gpt-4o" value={modelId} onChange={(e) => setModelId(e.target.value)} required className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-text-secondary">Endpoint URL <span className="text-text-secondary/60">(optional)</span></label>
                    <input placeholder="https://..." value={endpointUrl} onChange={(e) => setEndpointUrl(e.target.value)} className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary" />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => { setShowAdd(false); setCustomMode(false) }} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-white">Cancel</button>
                  <button type="submit" disabled={createModel.isPending} className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">{createModel.isPending ? 'Adding...' : 'Add Model'}</button>
                </div>
              </form>
            )}

            <div className="flex justify-end border-t border-border px-3 py-2">
              <button onClick={() => { setShowAdd(false); setCustomMode(false) }} className="text-xs text-text-secondary hover:text-text">Close</button>
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
        ) : list.length === 0 ? (
          <p className="text-sm text-text-secondary text-center py-6">No AI models configured</p>
        ) : (
          <div className="space-y-2">
            {list.map((model) => (
              <div key={model.id} className={cn('flex items-center justify-between rounded-lg border p-4 transition-colors', model.is_active ? 'border-primary/30 bg-primary/5' : 'border-border')}>
                <div className="flex items-center gap-3">
                  <span className="text-xl">{providerIcons[model.provider] || '🤖'}</span>
                  <div>
                    <p className="text-sm font-semibold text-text">{model.name}</p>
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                      <span className="uppercase tracking-wider font-medium">{model.provider}</span>
                      <span className="font-mono bg-surface-alt px-1.5 py-0.5 rounded text-[10px]">{model.model_id}</span>
                    </div>
                    {model.endpoint_url && <p className="text-[10px] text-text-secondary/60 mt-0.5 font-mono">{model.endpoint_url}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => deleteModel.mutate(model.id)} className="rounded-lg p-1.5 text-text-secondary hover:text-danger hover:bg-red-50 transition-colors" title="Delete model"><Trash2 className="h-3.5 w-3.5" /></button>
                  <button
                    onClick={() => toggleModel.mutate(model.id)}
                    disabled={toggleModel.isPending}
                    className={cn('rounded-lg px-3 py-1.5 text-xs font-medium transition-colors', model.is_active ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200')}
                  >
                    {model.is_active ? 'Active' : 'Disabled'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-text mb-1">AI Knowledge Base (RAG)</h2>
        <p className="text-xs text-text-secondary mb-4">The AI assistant uses vector embeddings of your workspace data to provide accurate answers. Re-index if data appears stale or after bulk imports.</p>

        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-alt p-4">
          <div>
            <p className="text-sm font-medium text-text">Indexed Documents</p>
            <p className="text-2xl font-bold text-primary mt-0.5">{capabilities?.indexed_documents ?? '—'}</p>
          </div>
          <button
            onClick={() => { setReindexStatus('running'); reindexMutation.mutate() }}
            disabled={reindexStatus === 'running'}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50 flex items-center gap-2"
          >
            {reindexStatus === 'running' && <Loader2 className="h-4 w-4 animate-spin" />}
            {reindexStatus === 'running' ? 'Re-indexing…' : 'Re-index All Data'}
          </button>
        </div>

        {reindexStatus === 'done' && reindexResult !== null && (
          <p className="mt-3 text-sm text-emerald-600 font-medium">Re-indexing complete — {reindexResult} documents indexed.</p>
        )}
        {reindexStatus === 'error' && (
          <p className="mt-3 text-sm text-red-600 font-medium">Re-indexing failed. Please try again or check server logs.</p>
        )}
      </div>
    </div>
  )
}
