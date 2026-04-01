/**
 * ChatPanel — Global slide-in AI chat panel.
 *
 * Features:
 * - Reads context from chatStore (workspace or project level)
 * - Workspace-level: cross-project questions, no tool execution
 * - Project-level: conversational AI + tool calls + suggest plan + weekly summary
 * - Auto-refreshes queries when AI makes changes
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatStore } from '@/stores/chatStore'
import {
  X, Send, Loader2, Bot, User, Sparkles,
  AlertTriangle, CheckCircle2, Lightbulb,
  FolderKanban, Building2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ──

interface ToolCallResult {
  tool: string
  input: Record<string, unknown>
  result: Record<string, unknown>
  success: boolean
  error?: string | null
}

interface ChatResponse {
  message: string
  tool_calls: ToolCallResult[]
  updated_entities: string[]
}

interface SuggestPlanResponse {
  suggested_objectives: { title: string; suggested_weeks: string[] }[]
  explanation: string
  commit_token: string
}

interface WeeklySummaryResponse {
  summary: string
  at_risk: string[]
  on_track: string[]
  blocked: string[]
  suggested_actions: string[]
}

// ── Entity → query key mapping ──
const ENTITY_QUERY_MAP: Record<string, string> = {
  oppm_objectives: 'oppm-objectives',
  oppm_timeline_entries: 'oppm-timeline',
  oppm_costs: 'oppm-costs',
  tasks: 'tasks',
  projects: 'project',
}

export function ChatPanel() {
  const [input, setInput] = useState('')
  const [pendingPlan, setPendingPlan] = useState<SuggestPlanResponse | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const isOpen = useChatStore((s) => s.isOpen)
  const messages = useChatStore((s) => s.messages)
  const contextType = useChatStore((s) => s.contextType)
  const projectId = useChatStore((s) => s.projectId)
  const projectTitle = useChatStore((s) => s.projectTitle)
  const addMessage = useChatStore((s) => s.addMessage)
  const close = useChatStore((s) => s.close)

  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const queryClient = useQueryClient()

  const isProjectContext = contextType === 'project' && !!projectId

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 200)
  }, [isOpen])

  // Invalidate queries for updated entities
  const invalidateEntities = useCallback(
    (entities: string[]) => {
      for (const entity of entities) {
        const queryKey = ENTITY_QUERY_MAP[entity]
        if (queryKey && projectId) {
          queryClient.invalidateQueries({ queryKey: [queryKey, projectId] })
        }
      }
    },
    [queryClient, projectId],
  )

  // ── Chat mutation ──
  const chatMutation = useMutation({
    mutationFn: (msgs: { role: string; content: string }[]) => {
      const path = isProjectContext
        ? `${wsPath}/projects/${projectId}/ai/chat`
        : `${wsPath}/ai/chat`
      return api.post<ChatResponse>(path, { messages: msgs })
    },
    onSuccess: (data) => {
      addMessage({
        role: 'assistant',
        content: data.message,
        toolCalls: data.tool_calls,
        updatedEntities: data.updated_entities,
      })
      if (data.updated_entities.length > 0) {
        invalidateEntities(data.updated_entities)
      }
    },
    onError: (err: Error) => {
      addMessage({ role: 'assistant', content: `Error: ${err.message}` })
    },
  })

  // ── Suggest plan mutation (project-only) ──
  const suggestPlanMutation = useMutation({
    mutationFn: (description: string) =>
      api.post<SuggestPlanResponse>(`${wsPath}/projects/${projectId}/ai/suggest-plan`, { description }),
    onSuccess: (data) => {
      setPendingPlan(data)
      const objList = data.suggested_objectives.map((o, i) => `${i + 1}. ${o.title} (${o.suggested_weeks.join(', ')})`).join('\n')
      addMessage({
        role: 'assistant',
        content: `${data.explanation}\n\n**Suggested objectives:**\n${objList}\n\nClick "Apply Plan" to create these objectives, or "Discard" to cancel.`,
      })
    },
    onError: (err: Error) => {
      addMessage({ role: 'assistant', content: `Error generating plan: ${err.message}` })
    },
  })

  // ── Commit plan mutation ──
  const commitPlanMutation = useMutation({
    mutationFn: (commitToken: string) =>
      api.post<{ created_objectives: unknown[]; count: number }>(
        `${wsPath}/projects/${projectId}/ai/suggest-plan/commit`,
        { commit_token: commitToken },
      ),
    onSuccess: (data) => {
      setPendingPlan(null)
      addMessage({ role: 'assistant', content: `Plan applied! Created ${data.count} objectives.` })
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', projectId] })
      queryClient.invalidateQueries({ queryKey: ['oppm-timeline', projectId] })
    },
    onError: (err: Error) => {
      addMessage({ role: 'assistant', content: `Error applying plan: ${err.message}` })
    },
  })

  // ── Weekly summary mutation (project-only) ──
  const weeklySummaryMutation = useMutation({
    mutationFn: () =>
      api.get<WeeklySummaryResponse>(`${wsPath}/projects/${projectId}/ai/weekly-summary`),
    onSuccess: (data) => {
      const parts = [data.summary]
      if (data.at_risk.length) parts.push(`\n**At Risk:** ${data.at_risk.length} objective(s)`)
      if (data.blocked.length) parts.push(`**Blocked:** ${data.blocked.length} objective(s)`)
      if (data.on_track.length) parts.push(`**On Track:** ${data.on_track.length} objective(s)`)
      if (data.suggested_actions.length) {
        parts.push('\n**Suggested Actions:**')
        data.suggested_actions.forEach((a, i) => parts.push(`${i + 1}. ${a}`))
      }
      addMessage({ role: 'assistant', content: parts.join('\n') })
    },
    onError: (err: Error) => {
      addMessage({ role: 'assistant', content: `Error: ${err.message}` })
    },
  })

  // ── Send message handler ──
  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || chatMutation.isPending) return

    addMessage({ role: 'user', content: text })
    setInput('')

    const allMsgs = [...messages, { role: 'user' as const, content: text }]
    chatMutation.mutate(
      allMsgs.map((m) => ({ role: m.role, content: m.content })),
    )
  }, [input, messages, chatMutation, addMessage])

  const isLoading =
    chatMutation.isPending ||
    suggestPlanMutation.isPending ||
    commitPlanMutation.isPending ||
    weeklySummaryMutation.isPending

  if (!isOpen) return null

  return (
    <div className="fixed top-0 right-0 h-full w-[420px] bg-white border-l border-gray-200 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-blue-600" />
          <span className="font-semibold text-sm text-gray-800">OPPM AI Assistant</span>
        </div>
        <button onClick={close} className="text-gray-400 hover:text-gray-600">
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Context badge */}
      <div className="flex items-center gap-2 px-4 py-1.5 border-b border-gray-100 bg-gray-50/50 text-xs text-gray-500">
        {isProjectContext ? (
          <>
            <FolderKanban className="h-3.5 w-3.5 text-blue-500" />
            <span>Project: <span className="font-medium text-gray-700">{projectTitle || 'Untitled'}</span></span>
          </>
        ) : (
          <>
            <Building2 className="h-3.5 w-3.5 text-purple-500" />
            <span>Workspace: <span className="font-medium text-gray-700">{ws?.name || 'All'}</span></span>
          </>
        )}
      </div>

      {/* Quick Actions (project-only) */}
      {isProjectContext && (
        <div className="flex gap-2 px-4 py-2 border-b border-gray-100 bg-gray-50/50">
          <button
            onClick={() => {
              const desc = prompt('Describe the project goals for AI plan generation:')
              if (desc) {
                addMessage({ role: 'user', content: `Generate a plan: ${desc}` })
                suggestPlanMutation.mutate(desc)
              }
            }}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-xs bg-blue-50 text-blue-700 rounded-full px-3 py-1.5 hover:bg-blue-100 disabled:opacity-50 font-medium"
          >
            <Sparkles className="h-3 w-3" />
            Suggest Plan
          </button>
          <button
            onClick={() => {
              addMessage({ role: 'user', content: 'Generate weekly summary' })
              weeklySummaryMutation.mutate()
            }}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-xs bg-purple-50 text-purple-700 rounded-full px-3 py-1.5 hover:bg-purple-100 disabled:opacity-50 font-medium"
          >
            <Lightbulb className="h-3 w-3" />
            Weekly Summary
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm mt-12">
            <Bot className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            <p className="font-medium text-gray-500">
              {isProjectContext ? 'Ask me about your project' : 'Ask me about your workspace'}
            </p>
            <p className="text-xs mt-1">
              {isProjectContext
                ? 'I can update objectives, timelines, generate plans, and analyze progress.'
                : 'I can answer questions across all projects, tasks, and team members.'}
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn(
              'flex gap-2',
              msg.role === 'user' ? 'justify-end' : 'justify-start',
            )}
          >
            {msg.role === 'assistant' && (
              <Bot className="h-5 w-5 text-blue-500 shrink-0 mt-1" />
            )}
            <div
              className={cn(
                'max-w-[85%] rounded-xl px-3 py-2 text-sm',
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-800',
              )}
            >
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>

              {/* Tool call results */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="mt-2 space-y-1 border-t border-gray-200 pt-2">
                  {msg.toolCalls.map((tc, j) => (
                    <div
                      key={j}
                      className={cn(
                        'flex items-center gap-1.5 text-xs rounded px-2 py-1',
                        tc.success
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-red-50 text-red-700',
                      )}
                    >
                      {tc.success ? (
                        <CheckCircle2 className="h-3 w-3 shrink-0" />
                      ) : (
                        <AlertTriangle className="h-3 w-3 shrink-0" />
                      )}
                      <span className="font-medium">{tc.tool}</span>
                      {tc.error && <span className="ml-1">— {tc.error}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <User className="h-5 w-5 text-blue-500 shrink-0 mt-1" />
            )}
          </div>
        ))}

        {/* Pending plan buttons */}
        {pendingPlan && (
          <div className="flex gap-2 ml-7">
            <button
              onClick={() => commitPlanMutation.mutate(pendingPlan.commit_token)}
              disabled={commitPlanMutation.isPending}
              className="text-xs bg-emerald-600 text-white rounded-lg px-4 py-1.5 font-medium hover:bg-emerald-700 disabled:opacity-50"
            >
              {commitPlanMutation.isPending ? 'Applying…' : 'Apply Plan'}
            </button>
            <button
              onClick={() => {
                setPendingPlan(null)
                addMessage({ role: 'assistant', content: 'Plan discarded.' })
              }}
              className="text-xs text-gray-500 hover:text-gray-700 rounded-lg px-3 py-1.5 border border-gray-200"
            >
              Discard
            </button>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-400 ml-7">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking…
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder={
              isProjectContext
                ? 'Ask about your project…'
                : 'Ask about your workspace…'
            }
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 placeholder:text-gray-400"
            style={{ maxHeight: '120px' }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="rounded-xl bg-blue-600 p-2 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
