/**
 * ChatPanel — Global slide-in AI chat panel.
 *
 * Features:
 * - Reads context from chatStore (workspace or project level)
 * - Workspace-level: cross-project questions, no tool execution
 * - Project-level: conversational AI + tool calls + suggest plan + weekly summary
 * - File upload: .txt .md .csv .json .xml .yaml image/* .pdf .docx (text extracted client-side)
 * - Chat history persisted to localStorage per workspace/project context
 * - Auto-refreshes queries when AI makes changes
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, parseFile, executeSheetActions, getGoogleSheetSnapshot } from '@/lib/api'
import { fetchWithSessionRetry } from '@/lib/api/sessionClient'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatStore, getContextKey, type FileAttachment, type PastSession, DEFAULT_PANEL_SIZE } from '@/stores/chatStore'
import type { SheetAction, SheetActionResult } from '@/types'
import {
  X, Send, Loader2, Bot, User, Sparkles,
  AlertTriangle, CheckCircle2, Lightbulb,
  FolderKanban, Building2, Paperclip, FileText,
  ImageIcon, File, Clock, History, MessageSquarePlus, ChevronLeft, Trash2, Play,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ──

interface PendingAttachment {
  name: string
  type: 'text' | 'image' | 'binary'
  content: string   // text: raw text; image: data URL; binary: ''
  size: number
}

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
  low_confidence?: boolean
  iterations?: number
}

interface SuggestedPlanTask {
  title: string
  priority?: string | null
  suggested_weeks: string[]
  subtasks: string[]
}

interface SuggestedPlanHeader {
  project_leader?: string | null
  project_objective?: string | null
  deliverable_output?: string | null
  completed_by_text?: string | null
  people_count?: number | null
}

interface SuggestPlanResponse {
  header: SuggestedPlanHeader
  suggested_objectives: { title: string; suggested_weeks: string[]; tasks: SuggestedPlanTask[] }[]
  explanation: string
  commit_token: string
  existing_task_count: number
}

interface CommitPlanResponse {
  count: number
  objectives_created: number
  objectives_updated: number
  tasks_created: number
  tasks_updated: number
  timeline_entries_upserted: number
}

interface WeeklySummaryResponse {
  summary: string
  at_risk: string[]
  on_track: string[]
  blocked: string[]
  suggested_actions: string[]
}

// ── Constants ──

const ENTITY_QUERY_MAP: Record<string, string> = {
  oppm_objectives: 'oppm-objectives',
  oppm_timeline_entries: 'oppm-timeline',
  oppm_costs: 'oppm-costs',
  tasks: 'tasks',
  projects: 'project',
}

/** File extensions whose text content is extracted client-side */
const TEXT_EXTENSIONS = new Set([
  '.txt', '.md', '.csv', '.json', '.xml', '.yaml', '.yml', '.log',
  '.html', '.htm', '.py', '.js', '.ts', '.tsx', '.jsx', '.css', '.sh', '.sql',
])

const MAX_TEXT_CHARS = 10_000
const MAX_FILES_PER_MSG = 5
const MAX_FILE_BYTES = 10 * 1024 * 1024  // 10 MB

/** Binary extensions that the backend can extract text from */
const SERVER_PARSE_EXTENSIONS = new Set(['.xlsx', '.xls', '.pdf', '.docx', '.doc'])

// ── Helpers ──

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(1)} MB`
}

function fileExt(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = (e) => resolve(e.target?.result as string)
    r.onerror = () => reject(new Error(`Cannot read ${file.name}`))
    r.readAsText(file)
  })
}

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = (e) => resolve(e.target?.result as string)
    r.onerror = () => reject(new Error(`Cannot read ${file.name}`))
    r.readAsDataURL(file)
  })
}

function parseChoices(content: string): { displayContent: string; choices: string[]; hasCustom: boolean } {
  const match = content.match(/\[CHOICES:\s*([^\]]+)\]\s*$/)
  if (!match) return { displayContent: content, choices: [], hasCustom: false }
  const raw = match[1].split('|').map(s => s.trim()).filter(Boolean)
  const hasCustom = raw.length > 0 && raw[raw.length - 1].endsWith('...')
  const choices = hasCustom ? raw.slice(0, -1) : raw
  const displayContent = content.slice(0, match.index).trimEnd()
  return { displayContent, choices, hasCustom }
}

// ── Component ──

export function ChatPanel() {
  const [input, setInput] = useState('')
  const [pendingPlan, setPendingPlan] = useState<SuggestPlanResponse | null>(null)
  const [showPlanInput, setShowPlanInput] = useState(false)
  const [planGoal, setPlanGoal] = useState('')
  const [attachments, setAttachments] = useState<PendingAttachment[]>([])
  const [fileError, setFileError] = useState<string | null>(null)

  // Track if currently dragging/resizing to suppress text selection
  const [isDragging, setIsDragging] = useState(false)
  const [sessionStartIdx, setSessionStartIdx] = useState(0)
  const prevContextKeyRef = useRef('')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const planInputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isOpen = useChatStore((s) => s.isOpen)
  const messages = useChatStore((s) => s.messages)
  const contextType = useChatStore((s) => s.contextType)
  const projectId = useChatStore((s) => s.projectId)
  const projectTitle = useChatStore((s) => s.projectTitle)
  const addMessage = useChatStore((s) => s.addMessage)
  const clearContextHistory = useChatStore((s) => s.clearContextHistory)
  const close = useChatStore((s) => s.close)
  const panelPosition = useChatStore((s) => s.panelPosition)
  const panelSize = useChatStore((s) => s.panelSize)
  const setPanelGeometry = useChatStore((s) => s.setPanelGeometry)
  const saveAndNewChat = useChatStore((s) => s.saveAndNewChat)
  const restoreSession = useChatStore((s) => s.restoreSession)
  const deleteSession = useChatStore((s) => s.deleteSession)
  const pastSessions = useChatStore((s) => s.pastSessions)
  const oppmSheetSpreadsheetId = useChatStore((s) => s.oppmSheetSpreadsheetId)

  // ── History panel state ──
  const [showHistory, setShowHistory] = useState(false)

  // ── Drag / resize state ──
  const dragState = useRef<{ startMX: number; startMY: number; startX: number; startY: number } | null>(null)
  const resizeState = useRef<{
    edge: 'right' | 'bottom' | 'corner'
    startMX: number; startMY: number; startW: number; startH: number; startX: number; startY: number
  } | null>(null)
  // Live position/size tracked in refs during drag to avoid re-renders on every mousemove
  const livePos = useRef({ x: 0, y: 0 })
  const liveSize = useRef(DEFAULT_PANEL_SIZE)
  const panelRef = useRef<HTMLDivElement>(null)

  const MIN_W = 300
  const MIN_H = 300
  const MAX_W = 900

  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const queryClient = useQueryClient()

  const isProjectContext = contextType === 'project' && !!projectId
  const contextKey = getContextKey(contextType, projectId)
  const isOppmSheetMode = isProjectContext && !!projectId && !!oppmSheetSpreadsheetId && !!ws
  const sheetContext = isOppmSheetMode && ws && projectId
    ? { workspaceId: ws.id, projectId }
    : null

  // Capture session start index when context key changes (to mark restored history)
  useEffect(() => {
    if (contextKey !== prevContextKeyRef.current) {
      prevContextKeyRef.current = contextKey
      setSessionStartIdx(messages.length)
      setAttachments([])
      setFileError(null)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextKey])

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Initialize panel position to right edge on first mount (when no persisted position)
  useEffect(() => {
    const defaultX = Math.max(0, window.innerWidth - (panelSize.width + 20))
    const defaultY = 0
    const pos = panelPosition ?? { x: defaultX, y: defaultY }
    livePos.current = pos
    liveSize.current = panelSize
    if (panelRef.current) {
      panelRef.current.style.left = `${pos.x}px`
      panelRef.current.style.top = `${pos.y}px`
      panelRef.current.style.width = `${panelSize.width}px`
      panelRef.current.style.height = `${panelSize.height}px`
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  // Global drag mousemove/mouseup
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragState.current || !panelRef.current) return
      const { startMX, startMY, startX, startY } = dragState.current
      const dx = e.clientX - startMX
      const dy = e.clientY - startMY
      const maxX = window.innerWidth - liveSize.current.width
      const maxY = window.innerHeight - MIN_H
      const newX = Math.max(0, Math.min(maxX, startX + dx))
      const newY = Math.max(0, Math.min(maxY, startY + dy))
      livePos.current = { x: newX, y: newY }
      panelRef.current.style.left = `${newX}px`
      panelRef.current.style.top = `${newY}px`
    }
    function onUp() {
      if (!dragState.current) return
      dragState.current = null
      setIsDragging(false)
      setPanelGeometry(livePos.current, liveSize.current)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [setPanelGeometry])

  // Global resize mousemove/mouseup
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!resizeState.current || !panelRef.current) return
      const { edge, startMX, startMY, startW, startH } = resizeState.current
      const dx = e.clientX - startMX
      const dy = e.clientY - startMY
      const maxH = window.innerHeight - livePos.current.y
      let newW = liveSize.current.width
      let newH = liveSize.current.height
      if (edge === 'right' || edge === 'corner') {
        newW = Math.max(MIN_W, Math.min(MAX_W, startW + dx))
      }
      if (edge === 'bottom' || edge === 'corner') {
        newH = Math.max(MIN_H, Math.min(maxH, startH + dy))
      }
      liveSize.current = { width: newW, height: newH }
      panelRef.current.style.width = `${newW}px`
      panelRef.current.style.height = `${newH}px`
    }
    function onUp() {
      if (!resizeState.current) return
      resizeState.current = null
      setIsDragging(false)
      setPanelGeometry(livePos.current, liveSize.current)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [setPanelGeometry])

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 200)
  }, [isOpen])

  // Focus plan goal input when shown
  useEffect(() => {
    if (showPlanInput) setTimeout(() => planInputRef.current?.focus(), 50)
  }, [showPlanInput])

  // Invalidate queries for updated entities
  const invalidateEntities = useCallback(
    (entities: string[]) => {
      for (const entity of entities) {
        const queryKey = ENTITY_QUERY_MAP[entity]
        if (!queryKey) continue
        if (projectId) {
          // Project context: invalidate by projectId
          queryClient.invalidateQueries({ queryKey: [queryKey, projectId] })
        }
        // Workspace context: invalidate workspace-scoped queries (e.g. projects list)
        // Always run this so the Projects page refreshes in real time after create_project
        if (ws?.id) {
          queryClient.invalidateQueries({ queryKey: [queryKey, ws.id] })
        }
      }
    },
    [queryClient, projectId, ws?.id],
  )

  // ── File handling ──

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? [])
      e.target.value = ''
      setFileError(null)

      const remaining = MAX_FILES_PER_MSG - attachments.length
      if (remaining <= 0) {
        setFileError(`Maximum ${MAX_FILES_PER_MSG} files per message.`)
        return
      }
      const toProcess = files.slice(0, remaining)
      if (files.length > remaining) {
        setFileError(`Only the first ${remaining} file(s) added (max ${MAX_FILES_PER_MSG}).`)
      }

      const results: PendingAttachment[] = []
      for (const file of toProcess) {
        const ext = fileExt(file.name)
        try {
          if (file.size > MAX_FILE_BYTES) {
            setFileError(`${file.name} exceeds 10 MB limit.`)
            continue
          }
          if (file.type.startsWith('image/')) {
            const dataUrl = await readAsDataURL(file)
            results.push({ name: file.name, type: 'image', content: dataUrl, size: file.size })
          } else if (TEXT_EXTENSIONS.has(ext) || file.type.startsWith('text/')) {
            const text = await readAsText(file)
            results.push({ name: file.name, type: 'text', content: text, size: file.size })
          } else if (SERVER_PARSE_EXTENSIONS.has(ext) && ws) {
            // Send binary file to backend for text extraction
            const parsed = await parseFile(ws.id, file)
            if (parsed.error) {
              setFileError(`${file.name}: ${parsed.error}`)
              continue
            }
            results.push({ name: file.name, type: 'text', content: parsed.extracted_text, size: file.size })
            if (parsed.truncated) {
              setFileError(`${file.name} was truncated due to size.`)
            }
          } else {
            // Unsupported binary — store stub
            results.push({ name: file.name, type: 'binary', content: '', size: file.size })
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Unknown error'
          setFileError(`Failed to process ${file.name}: ${msg}`)
        }
      }
      setAttachments((prev) => [...prev, ...results])
    },
    [attachments.length, ws],
  )

  const removeAttachment = useCallback((idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx))
  }, [])

  // ── Streaming chat ──

  const [isChatPending, setIsChatPending] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const sendChat = useCallback(
    async (msgs: { role: string; content: string }[]) => {
      if (!ws) return
      setIsChatPending(true)
      abortRef.current = new AbortController()

      // OPPM sheet mode: blocking POST with oppm_sheet_mode flag, no SSE streaming
      const isOppmSheetMode = isProjectContext && !!projectId && !!oppmSheetSpreadsheetId
      if (isOppmSheetMode) {
        try {
          // Fetch live sheet snapshot so the AI can see current borders/colors/values
          let snapshot: Record<string, unknown> | undefined
          try {
            snapshot = await getGoogleSheetSnapshot(ws.id, projectId)
          } catch (snapErr) {
            console.warn('Failed to fetch sheet snapshot:', snapErr)
          }

          const payload: Record<string, unknown> = {
            messages: msgs,
            oppm_sheet_mode: true,
            spreadsheet_id: oppmSheetSpreadsheetId,
          }
          if (snapshot) {
            payload.sheet_snapshot = snapshot
          }

          const data = await api.post<ChatResponse>(
            `${wsPath}/projects/${projectId}/ai/chat`,
            payload,
          )
          addMessage({
            role: 'assistant',
            content: data.message,
            toolCalls: [],
            updatedEntities: [],
            lowConfidence: false,
          })
        } catch (err) {
          addMessage({ role: 'assistant', content: `Error: ${err instanceof Error ? err.message : String(err)}` })
        } finally {
          setIsChatPending(false)
          abortRef.current = null
        }
        return
      }

      // Project-level uses the streaming endpoint; workspace-level falls back to blocking POST
      const isStreamable = isProjectContext && !!projectId
      const path = isStreamable
        ? `${wsPath}/projects/${projectId}/ai/chat/stream`
        : `${wsPath}/ai/chat`

      if (!isStreamable) {
        // Workspace-level: blocking POST (no streaming endpoint yet)
        try {
          const data = await api.post<ChatResponse>(path, { messages: msgs })
          addMessage({
            role: 'assistant',
            content: data.message,
            toolCalls: data.tool_calls,
            updatedEntities: data.updated_entities,
            lowConfidence: data.low_confidence ?? false,
          })
          if (data.updated_entities.length > 0) invalidateEntities(data.updated_entities)
        } catch (err) {
          addMessage({ role: 'assistant', content: `Error: ${err instanceof Error ? err.message : String(err)}` })
        } finally {
          setIsChatPending(false)
        }
        return
      }

      // Project-level: consume SSE stream
      // Use fetchWithSessionRetry so an expired access token is automatically
      // refreshed before the request rather than returning 401 to the user.
      try {
        const res = await fetchWithSessionRetry(path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: msgs }),
          signal: abortRef.current.signal,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || 'AI chat failed')
        }

        const reader = res.body?.getReader()
        if (!reader) throw new Error('No response body')
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          // Split on double-newline SSE boundary
          const parts = buffer.split('\n\n')
          buffer = parts.pop() ?? ''

          for (const part of parts) {
            const lines = part.split('\n')
            let event = 'message'
            let dataStr = ''
            for (const line of lines) {
              if (line.startsWith('event: ')) event = line.slice(7).trim()
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim()
            }
            if (!dataStr) continue

            try {
              const payload = JSON.parse(dataStr)
              if (event === 'tool_call' && payload.updated_entities?.length > 0) {
                invalidateEntities(payload.updated_entities as string[])
              } else if (event === 'message') {
                const data = payload as ChatResponse
                addMessage({
                  role: 'assistant',
                  content: data.message,
                  toolCalls: data.tool_calls,
                  updatedEntities: data.updated_entities,
                  lowConfidence: data.low_confidence ?? false,
                })
                if (data.updated_entities.length > 0) invalidateEntities(data.updated_entities)
              } else if (event === 'error') {
                addMessage({ role: 'assistant', content: `Error: ${payload.detail ?? 'Unknown error'}` })
              }
            } catch {
              // malformed SSE chunk — ignore
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          addMessage({ role: 'assistant', content: `Error: ${err.message}` })
        }
      } finally {
        setIsChatPending(false)
        abortRef.current = null
      }
    },
    [ws, isProjectContext, projectId, wsPath, addMessage, invalidateEntities, oppmSheetSpreadsheetId],
  )

  // ── Suggest plan mutation ──

  const suggestPlanMutation = useMutation({
    mutationFn: (description: string) =>
      api.post<SuggestPlanResponse>(
        `${wsPath}/projects/${projectId}/ai/suggest-plan`,
        { description },
      ),
    onSuccess: (data) => {
      const normalizedPlan: SuggestPlanResponse = {
        ...data,
        header: data.header ?? {},
        suggested_objectives: (data.suggested_objectives ?? []).map((objective) => ({
          ...objective,
          tasks: objective.tasks ?? [],
        })),
        existing_task_count: data.existing_task_count ?? 0,
      }
      setPendingPlan(normalizedPlan)
      const taskCount = normalizedPlan.suggested_objectives.reduce((count, objective) => count + objective.tasks.length, 0)
      const objList = normalizedPlan.suggested_objectives
        .map((o, i) => {
          const weeks = o.suggested_weeks.length > 0 ? o.suggested_weeks.join(', ') : 'No weeks suggested'
          const tasks = o.tasks.length > 0 ? `\n   Tasks: ${o.tasks.map((task) => task.title).join(', ')}` : ''
          return `${i + 1}. ${o.title} (${weeks})${tasks}`
        })
        .join('\n')
      const headerLines = [
        normalizedPlan.header.project_objective ? `**Objective:** ${normalizedPlan.header.project_objective}` : null,
        normalizedPlan.header.deliverable_output ? `**Deliverable:** ${normalizedPlan.header.deliverable_output}` : null,
        normalizedPlan.header.project_leader ? `**Leader:** ${normalizedPlan.header.project_leader}` : null,
      ].filter(Boolean)
      addMessage({
        role: 'assistant',
        content: `${normalizedPlan.explanation}\n\n${headerLines.join('\n')}\n\n**Suggested objectives:**\n${objList}\n\nCurrent project tasks considered: ${normalizedPlan.existing_task_count}\nSuggested root tasks: ${taskCount}\n\nClick "Apply Plan" to commit this native OPPM draft, or "Discard" to cancel.`,
      })
    },
    onError: (err: Error) => {
      addMessage({ role: 'assistant', content: `Error generating plan: ${err.message}` })
    },
  })

  // ── Commit plan mutation ──

  const commitPlanMutation = useMutation({
    mutationFn: (commitToken: string) =>
      api.post<CommitPlanResponse>(
        `${wsPath}/projects/${projectId}/ai/suggest-plan/commit`,
        { commit_token: commitToken },
      ),
    onSuccess: (data) => {
      setPendingPlan(null)
      addMessage({
        role: 'assistant',
        content: `Plan applied. Objectives touched: ${data.count}. Tasks created: ${data.tasks_created}. Tasks updated: ${data.tasks_updated}. Timeline rows upserted: ${data.timeline_entries_upserted}.`,
      })
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      queryClient.invalidateQueries({ queryKey: ['oppm-objectives', projectId] })
      queryClient.invalidateQueries({ queryKey: ['oppm-timeline', projectId] })
    },
    onError: (err: Error) => {
      addMessage({ role: 'assistant', content: `Error applying plan: ${err.message}` })
    },
  })

  // ── Weekly summary mutation ──

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
    if ((!text && attachments.length === 0) || isChatPending) return
    if (!ws) return

    // Build attachments saved to chatStore (images stored as data URL, text stored as empty to save space)
    const storedAttachments: FileAttachment[] = attachments.map((a) => ({
      name: a.name,
      type: a.type,
      content: a.type === 'image' ? a.content : '',
    }))

    // Display content is just what the user typed
    addMessage({
      role: 'user',
      content: text || '(attached files)',
      ...(storedAttachments.length > 0 ? { attachments: storedAttachments } : {}),
    })

    // Build API content — embed file contents only for this message
    let apiContent = text
    if (attachments.length > 0) {
      const blocks = attachments.map((a) => {
        if (a.type === 'text') {
          const body = a.content.length > MAX_TEXT_CHARS
            ? a.content.slice(0, MAX_TEXT_CHARS) + '\n… (truncated)'
            : a.content
          return `[File: ${a.name}]\n\`\`\`\n${body}\n\`\`\``
        }
        if (a.type === 'image') {
          return `[Image attached: ${a.name}]`
        }
        return `[Attached: ${a.name} — binary file, content extraction not supported]`
      })
      apiContent = [text, '\n\n--- Attached Files ---', ...blocks]
        .filter(Boolean)
        .join('\n')
    }

    setInput('')
    setAttachments([])
    setFileError(null)

    // Pass history messages + new user message to the API
    const allMsgs = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: 'user' as const, content: apiContent },
    ]
    sendChat(allMsgs)
  }, [input, attachments, messages, isChatPending, sendChat, addMessage, ws])

  const handleQuickSend = useCallback((text: string) => {
    if (!text.trim()) return
    addMessage({ role: 'user', content: text })
    const allMsgs = [
      ...messages.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })),
      { role: 'user' as const, content: text },
    ]
    sendChat(allMsgs)
  }, [messages, sendChat, addMessage])

  const handleSuggestPlan = useCallback(() => {
    const goal = planGoal.trim()
    if (!goal) return
    setShowPlanInput(false)
    setPlanGoal('')
    addMessage({ role: 'user', content: `Generate a plan: ${goal}` })
    suggestPlanMutation.mutate(goal)
  }, [planGoal, addMessage, suggestPlanMutation])

  const isLoading =
    isChatPending ||
    suggestPlanMutation.isPending ||
    commitPlanMutation.isPending ||
    weeklySummaryMutation.isPending

  if (!isOpen) return null

  return (
    <div
      ref={panelRef}
      className={cn(
        'fixed bg-white border border-border shadow-lg z-50 flex flex-col rounded-lg overflow-hidden',
        isDragging && 'select-none',
      )}
      style={{
        left: panelPosition ? panelPosition.x : Math.max(0, window.innerWidth - (panelSize.width + 20)),
        top: panelPosition ? panelPosition.y : 0,
        width: panelSize.width,
        height: panelSize.height,
        minWidth: MIN_W,
        minHeight: MIN_H,
      }}
    >

      {/* Header — drag handle */}
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-surface-alt cursor-move shrink-0"
        onMouseDown={(e) => {
          // Don't start drag on buttons inside header
          if ((e.target as HTMLElement).closest('button')) return
          e.preventDefault()
          setIsDragging(true)
          dragState.current = {
            startMX: e.clientX,
            startMY: e.clientY,
            startX: livePos.current.x,
            startY: livePos.current.y,
          }
        }}
      >
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-text-secondary" />
          <span className="font-semibold text-sm text-text">OPPM AI Assistant</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowHistory((v) => !v)}
            title="View history"
            className={cn(
              'p-1.5 rounded-md transition-colors',
              showHistory
                ? 'bg-surface-alt text-text'
                : 'text-text-secondary hover:text-text hover:bg-surface-alt',
            )}
          >
            <History className="h-4 w-4" />
          </button>
          <button
            onClick={() => { saveAndNewChat(); setShowHistory(false) }}
            title="New chat"
            className="p-1.5 text-text-secondary hover:text-text hover:bg-surface-alt rounded-md transition-colors"
          >
            <MessageSquarePlus className="h-4 w-4" />
          </button>
          <button onClick={close} className="p-1.5 text-text-secondary hover:text-text rounded-md">
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* ── History overlay ── */}
      {showHistory && (
        <div className="absolute inset-0 z-30 flex flex-col bg-white rounded-lg overflow-hidden">
          {/* History header */}
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-surface-alt shrink-0">
            <button
              onClick={() => setShowHistory(false)}
              className="p-1 text-text-secondary hover:text-text rounded-md"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <History className="h-4 w-4 text-text-secondary" />
            <span className="font-semibold text-sm text-text">Chat History</span>
            <span className="ml-auto text-xs text-text-secondary">
              {(pastSessions[contextKey] ?? []).length} session{(pastSessions[contextKey] ?? []).length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Session list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {(pastSessions[contextKey] ?? []).length === 0 ? (
              <div className="text-center text-text-secondary text-sm mt-12">
                <History className="h-10 w-10 mx-auto mb-3 text-border" />
                <p className="font-medium text-text-secondary">No past sessions</p>
                <p className="text-xs mt-1">Start a new chat and past conversations will appear here.</p>
              </div>
            ) : (
              (pastSessions[contextKey] ?? []).map((session: PastSession, idx: number) => {
                const firstUser = session.messages.find((m) => m.role === 'user')
                const preview = firstUser?.content?.slice(0, 80) ?? '(empty)'
                const date = new Date(session.savedAt)
                const dateStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                const timeStr = date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
                return (
                  <div
                    key={idx}
                    className="group flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-surface-alt cursor-pointer transition-colors"
                    onClick={() => { restoreSession(contextKey, idx); setShowHistory(false) }}
                  >
                    <div className="shrink-0 mt-0.5 h-8 w-8 rounded-full bg-surface-alt border border-border flex items-center justify-center">
                      <Bot className="h-4 w-4 text-text-secondary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-text">{dateStr} · {timeStr}</span>
                        <span className="text-xs text-text-secondary shrink-0">{session.messages.length} msg{session.messages.length !== 1 ? 's' : ''}</span>
                      </div>
                      <p className="text-xs text-text-secondary mt-0.5 truncate">{preview}</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteSession(contextKey, idx) }}
                      title="Delete session"
                      className="shrink-0 p-1 opacity-0 group-hover:opacity-100 text-text-secondary hover:text-danger rounded transition-all"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )
              })
            )}
          </div>

          {/* New Chat from history screen */}
          <div className="shrink-0 px-4 py-2.5 border-t border-border">
            <button
              onClick={() => { saveAndNewChat(); setShowHistory(false) }}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-dashed border-border py-2 text-sm font-medium text-text-secondary hover:border-text-secondary hover:text-text hover:bg-surface-alt transition-colors"
            >
              <MessageSquarePlus className="h-4 w-4" />
              New Chat
            </button>
          </div>
        </div>
      )}

      {/* Context badge */}
      <div className="flex items-center gap-2 px-4 py-1.5 border-b border-border bg-surface-alt/50 text-xs text-text-secondary">
        {isProjectContext ? (
          <>
            <FolderKanban className="h-3.5 w-3.5 text-text-secondary" />
            <span>Project: <span className="font-medium text-text">{projectTitle || 'Untitled'}</span></span>
          </>
        ) : (
          <>
            <Building2 className="h-3.5 w-3.5 text-text-secondary" />
            <span>Workspace: <span className="font-medium text-text">{ws?.name || 'All'}</span></span>
          </>
        )}
      </div>

      {/* Quick Actions (project-only) */}
      {isProjectContext && (
        <div className="flex gap-2 px-4 py-2 border-b border-border bg-surface-alt/50">
          <button
            onClick={() => setShowPlanInput(true)}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-xs bg-surface-alt text-text rounded-full px-3 py-1.5 hover:bg-border disabled:opacity-50 font-medium"
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
            className="flex items-center gap-1.5 text-xs bg-surface-alt text-text rounded-full px-3 py-1.5 hover:bg-border disabled:opacity-50 font-medium"
          >
            <Lightbulb className="h-3 w-3" />
            Weekly Summary
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">

        {/* History indicator */}
        {sessionStartIdx > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-px bg-border" />
            <span className="flex items-center gap-1 text-xs text-text-secondary shrink-0">
              <Clock className="h-3 w-3" />
              {sessionStartIdx} previous message{sessionStartIdx !== 1 ? 's' : ''}
            </span>
            <div className="flex-1 h-px bg-border" />
          </div>
        )}

        {/* Empty state */}
        {messages.length === 0 && (
          <div className="text-center text-text-secondary text-sm mt-12">
            <Bot className="h-10 w-10 mx-auto mb-3 text-border" />
            {!ws ? (
              <>
                <p className="font-medium text-text-secondary">No workspace selected</p>
                <p className="text-xs mt-1">Select a workspace from the sidebar to start chatting with the AI assistant.</p>
              </>
            ) : (
              <>
                <p className="font-medium text-text-secondary">
                  {isProjectContext ? 'Ask me about your project' : 'Ask me about your workspace'}
                </p>
                <p className="text-xs mt-1">
                  {isProjectContext
                    ? 'I can update objectives, timelines, generate plans, and analyze progress.'
                    : 'I can answer questions across all projects, tasks, and team members.'}
                </p>
                <p className="text-xs mt-2 text-text-secondary">
                  Attach files with the <Paperclip className="inline h-3 w-3" /> button below.
                </p>
              </>
            )}
          </div>
        )}

        {/* New session divider (when there is restored history) */}
        {sessionStartIdx > 0 && messages.length > sessionStartIdx && (
          <>
            {messages.slice(0, sessionStartIdx).map((msg, i) => (
              <MessageBubble key={`h-${i}`} msg={msg} />
            ))}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-text-secondary shrink-0">New session</span>
              <div className="flex-1 h-px bg-border" />
            </div>
            {messages.slice(sessionStartIdx).map((msg, i, arr) => (
              <MessageBubble
                key={`n-${i}`}
                msg={msg}
                onChoiceSelect={i === arr.length - 1 ? handleQuickSend : undefined}
                sheetContext={sheetContext}
              />
            ))}
          </>
        )}

        {/* All messages when no divider needed */}
        {(sessionStartIdx === 0 || messages.length <= sessionStartIdx) &&
          messages.map((msg, i, arr) => (
            <MessageBubble
              key={i}
              msg={msg}
              onChoiceSelect={i === arr.length - 1 ? handleQuickSend : undefined}
              sheetContext={sheetContext}
            />
          ))}

        {/* Pending plan buttons */}
        {pendingPlan && (
          <div className="flex gap-2 ml-7">
            <button
              onClick={() => commitPlanMutation.mutate(pendingPlan.commit_token)}
              disabled={commitPlanMutation.isPending}
              className="text-xs bg-primary text-white rounded-md px-4 py-1.5 font-medium hover:bg-primary-dark disabled:opacity-50"
            >
              {commitPlanMutation.isPending ? 'Applying…' : 'Apply Plan'}
            </button>
            <button
              onClick={() => {
                setPendingPlan(null)
                addMessage({ role: 'assistant', content: 'Plan discarded.' })
              }}
              className="text-xs text-text-secondary hover:text-text rounded-md px-3 py-1.5 border border-border"
            >
              Discard
            </button>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-text-secondary ml-7">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking…
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border px-4 pt-2 pb-3">

        {/* Pending attachment chips */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {attachments.map((att, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 bg-surface-alt border border-border text-xs rounded-full px-2.5 py-1 max-w-[160px]"
              >
                {att.type === 'image' ? (
                  <ImageIcon className="h-3 w-3 text-text-secondary shrink-0" />
                ) : att.type === 'text' ? (
                  <FileText className="h-3 w-3 text-text-secondary shrink-0" />
                ) : (
                  <File className="h-3 w-3 text-text-secondary shrink-0" />
                )}
                <span className="truncate text-text">{att.name}</span>
                <span className="text-text-secondary shrink-0">({formatBytes(att.size)})</span>
                <button
                  onClick={() => removeAttachment(i)}
                  className="text-text-secondary hover:text-text shrink-0 ml-0.5"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* File error */}
        {fileError && (
          <p className="text-xs text-warning mb-1.5">{fileError}</p>
        )}

        {showPlanInput ? (
          <div className="space-y-2">
            <p className="text-xs font-medium text-text-secondary">Describe the project goals for AI plan generation:</p>
            <div className="flex items-center gap-2">
              <input
                ref={planInputRef}
                value={planGoal}
                onChange={(e) => setPlanGoal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { e.preventDefault(); handleSuggestPlan() }
                  if (e.key === 'Escape') { setShowPlanInput(false); setPlanGoal('') }
                }}
                placeholder="e.g. Build a healthcare data platform…"
                className="flex-1 rounded-md border border-border bg-surface-alt px-3 py-2 text-sm outline-none focus:border-text-secondary focus:ring-1 focus:ring-text-secondary/20 placeholder:text-text-secondary"
              />
              <button
                onClick={handleSuggestPlan}
                disabled={!planGoal.trim()}
                className="rounded-md bg-primary p-2 text-white hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed"
                title="Generate plan"
              >
                <Sparkles className="h-4 w-4" />
              </button>
              <button
                onClick={() => { setShowPlanInput(false); setPlanGoal('') }}
                className="rounded-md border border-border p-2 text-text-secondary hover:bg-surface-alt"
                title="Cancel"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={attachments.length >= MAX_FILES_PER_MSG}
              title="Attach files"
              className={cn(
                'rounded-md border p-2 shrink-0 transition-colors',
                attachments.length >= MAX_FILES_PER_MSG
                  ? 'border-border text-text-secondary cursor-not-allowed'
                  : 'border-border text-text-secondary hover:bg-surface-alt hover:text-text',
              )}
            >
              <Paperclip className="h-4 w-4" />
            </button>
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
              onPaste={(e) => {
                const items = e.clipboardData?.items
                if (!items) return
                const imageItems: DataTransferItem[] = []
                for (let i = 0; i < items.length; i++) {
                  if (items[i].type.startsWith('image/')) {
                    imageItems.push(items[i])
                  }
                }
                if (imageItems.length === 0) return
                e.preventDefault()
                setFileError(null)
                const remaining = MAX_FILES_PER_MSG - attachments.length
                if (remaining <= 0) {
                  setFileError(`Maximum ${MAX_FILES_PER_MSG} files per message.`)
                  return
                }
                const toProcess = imageItems.slice(0, remaining)
                if (imageItems.length > remaining) {
                  setFileError(`Only the first ${remaining} image(s) added (max ${MAX_FILES_PER_MSG}).`)
                }
                Promise.all(
                  toProcess.map(async (item) => {
                    const file = item.getAsFile()
                    if (!file) return null
                    const dataUrl = await readAsDataURL(file)
                    return { name: file.name || 'pasted-image.png', type: 'image' as const, content: dataUrl, size: file.size }
                  }),
                ).then((results) => {
                  const valid = results.filter(Boolean) as PendingAttachment[]
                  setAttachments((prev) => [...prev, ...valid])
                })
              }}
              placeholder={
                !ws
                  ? 'Select a workspace to start chatting…'
                  : isProjectContext
                  ? 'Ask about your project… (Ctrl+V to paste image)'
                  : 'Ask about your workspace… (Ctrl+V to paste image)'
              }
              rows={1}
              className="flex-1 resize-none rounded-md border border-border bg-surface-alt px-3 py-2 text-sm outline-none focus:border-text-secondary focus:ring-1 focus:ring-text-secondary/20 placeholder:text-text-secondary"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={(!input.trim() && attachments.length === 0) || isLoading || !ws}
              className="rounded-md bg-primary p-2 text-white hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* hidden multi-file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          accept=".txt,.md,.csv,.json,.xml,.yaml,.yml,.log,.html,.htm,.py,.js,.ts,.tsx,.jsx,.css,.sh,.sql,.pdf,.docx,.doc,.xlsx,.xls,.pptx,image/*"
          onChange={handleFileChange}
        />
      </div>

      {/* ── Resize handles ── */}
      {/* Right edge */}
      <div
        className="absolute top-0 right-0 w-2 h-full cursor-ew-resize z-10"
        onMouseDown={(e) => {
          e.preventDefault()
          setIsDragging(true)
          resizeState.current = {
            edge: 'right',
            startMX: e.clientX, startMY: e.clientY,
            startW: liveSize.current.width, startH: liveSize.current.height,
            startX: livePos.current.x, startY: livePos.current.y,
          }
        }}
      />
      {/* Bottom edge */}
      <div
        className="absolute bottom-0 left-0 w-full h-2 cursor-ns-resize z-10"
        onMouseDown={(e) => {
          e.preventDefault()
          setIsDragging(true)
          resizeState.current = {
            edge: 'bottom',
            startMX: e.clientX, startMY: e.clientY,
            startW: liveSize.current.width, startH: liveSize.current.height,
            startX: livePos.current.x, startY: livePos.current.y,
          }
        }}
      />
      {/* Bottom-right corner */}
      <div
        className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize z-20"
        onMouseDown={(e) => {
          e.preventDefault()
          setIsDragging(true)
          resizeState.current = {
            edge: 'corner',
            startMX: e.clientX, startMY: e.clientY,
            startW: liveSize.current.width, startH: liveSize.current.height,
            startX: livePos.current.x, startY: livePos.current.y,
          }
        }}
      />
    </div>
  )
}

// ── SheetActionPreview sub-component ──

function tryParseSheetActions(content: string): SheetAction[] | null {
  try {
    const clean = content.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
    const parsed = JSON.parse(clean)
    if (
      Array.isArray(parsed) &&
      parsed.length > 0 &&
      typeof parsed[0] === 'object' &&
      'action' in parsed[0]
    ) {
      return parsed as SheetAction[]
    }
  } catch {
    // not JSON
  }
  return null
}

function SheetActionPreview({
  actions,
  workspaceId,
  projectId,
}: {
  actions: SheetAction[]
  workspaceId: string
  projectId: string
}) {
  const [results, setResults] = useState<SheetActionResult[] | null>(null)
  const [isApplying, setIsApplying] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)

  const handleApply = async () => {
    setIsApplying(true)
    setApplyError(null)
    try {
      const response = await executeSheetActions(workspaceId, projectId, actions)
      setResults(response.results)
      // Signal OPPMView (or any listener) to reload the embedded sheet
      window.dispatchEvent(new CustomEvent('oppm-sheet-actions-ran'))
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsApplying(false)
    }
  }

  return (
    <div className="mt-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-blue-800 text-xs uppercase tracking-wide">
          {actions.length} Sheet Action{actions.length !== 1 ? 's' : ''}
        </span>
        {!results && (
          <button
            onClick={handleApply}
            disabled={isApplying}
            className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded px-2.5 py-1 disabled:opacity-50"
          >
            {isApplying ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Apply to Sheet
          </button>
        )}
      </div>
      <ul className="space-y-1">
        {actions.map((action, i) => {
          const result = results?.[i]
          return (
            <li key={i} className="flex items-center gap-2 text-xs text-blue-700">
              {result ? (
                result.success ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="h-3 w-3 text-red-500 shrink-0" />
                )
              ) : (
                <span className="h-3 w-3 rounded-full border border-blue-400 shrink-0 inline-block" />
              )}
              <span className="font-mono font-medium text-blue-900">{action.action}</span>
              {result && !result.success && result.error && (
                <span className="text-red-500 ml-1">{result.error}</span>
              )}
            </li>
          )
        })}
      </ul>
      {applyError && (
        <p className="mt-2 text-xs text-red-600">{applyError}</p>
      )}
      {results && (
        <p className="mt-2 text-xs text-gray-500">
          {results.filter((r) => r.success).length} succeeded,{' '}
          {results.filter((r) => !r.success).length} failed
        </p>
      )}
    </div>
  )
}

// ── MessageBubble sub-component ──

function AttachmentChip({ att }: { att: FileAttachment }) {
  if (att.type === 'image') {
    return (
      <img
        src={att.content}
        alt={att.name}
        className="max-w-[200px] max-h-[140px] rounded-lg border border-white/30 object-cover mt-1"
      />
    )
  }
  return (
    <div className="inline-flex items-center gap-1.5 bg-white/20 text-xs rounded-full px-2.5 py-1 mt-1">
      {att.type === 'text' ? (
        <FileText className="h-3 w-3 shrink-0" />
      ) : (
        <File className="h-3 w-3 shrink-0" />
      )}
      <span className="max-w-[140px] truncate">{att.name}</span>
    </div>
  )
}

function MessageBubble({
  msg,
  onChoiceSelect,
  sheetContext,
}: {
  msg: { role: 'user' | 'assistant'; content: string; toolCalls?: ToolCallResult[]; attachments?: FileAttachment[]; lowConfidence?: boolean }
  onChoiceSelect?: (text: string) => void
  sheetContext?: { workspaceId: string; projectId: string } | null
}) {
  const [customInput, setCustomInput] = useState('')
  const { displayContent, choices, hasCustom } = msg.role === 'assistant'
    ? parseChoices(msg.content)
    : { displayContent: msg.content, choices: [], hasCustom: false }

  const sheetActions = msg.role === 'assistant' && sheetContext
    ? tryParseSheetActions(msg.content)
    : null
  return (
    <div
      className={cn(
        'flex gap-2',
        msg.role === 'user' ? 'justify-end' : 'justify-start',
      )}
    >
      {msg.role === 'assistant' && (
        <Bot className="h-5 w-5 text-blue-500 shrink-0 mt-1" />
      )}
      <div className="flex flex-col gap-2">
      <div
        className={cn(
          'max-w-[85%] rounded-xl px-3 py-2 text-sm',
          msg.role === 'user'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-800',
        )}
      >
        {/* Attachments (user messages) */}
        {msg.role === 'user' && msg.attachments && msg.attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {msg.attachments.map((att, i) => (
              <AttachmentChip key={i} att={att} />
            ))}
          </div>
        )}

        {/* Message content */}
        {msg.role === 'assistant' ? (
          sheetActions && sheetContext ? (
            <SheetActionPreview
              actions={sheetActions}
              workspaceId={sheetContext.workspaceId}
              projectId={sheetContext.projectId}
            />
          ) : (
          <div className="prose prose-sm max-w-none break-words
            prose-p:my-1 prose-p:leading-relaxed
            prose-headings:font-semibold prose-headings:mt-2 prose-headings:mb-1
            prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
            prose-strong:font-semibold prose-strong:text-gray-900
            prose-ul:my-1 prose-ul:pl-4 prose-ol:my-1 prose-ol:pl-4
            prose-li:my-0.5
            prose-code:bg-gray-200 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-mono
            prose-pre:bg-gray-200 prose-pre:rounded-lg prose-pre:p-2 prose-pre:text-xs prose-pre:overflow-x-auto
            prose-blockquote:border-l-2 prose-blockquote:border-gray-400 prose-blockquote:pl-2 prose-blockquote:italic prose-blockquote:text-gray-600
            prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {displayContent}
            </ReactMarkdown>
          </div>
          )
        ) : (
          <div className="whitespace-pre-wrap break-words">{msg.content}</div>
        )}

        {/* Low-confidence warning */}
        {msg.role === 'assistant' && msg.lowConfidence && (
          <div className="flex items-center gap-1.5 mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
            <AlertTriangle className="h-3 w-3 shrink-0" />
            <span>Low confidence — please verify this answer</span>
          </div>
        )}

        {/* Tool call results (assistant) */}
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
      {/* Choice buttons */}
      {onChoiceSelect && choices.length > 0 && (
        <div className="flex flex-wrap gap-2 max-w-[85%]">
          {choices.map((c, ci) => (
            <button
              key={ci}
              onClick={() => onChoiceSelect(c)}
              className="px-3 py-1.5 text-xs rounded-full border border-blue-300 bg-white text-blue-700 hover:bg-blue-50 transition-colors"
            >
              {c}
            </button>
          ))}
          {hasCustom && (
            <div className="flex gap-1 w-full mt-1">
              <input
                type="text"
                value={customInput}
                onChange={e => setCustomInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && customInput.trim()) {
                    onChoiceSelect(customInput.trim())
                    setCustomInput('')
                  }
                }}
                placeholder="Type your own..."
                className="flex-1 text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <button
                onClick={() => {
                  if (customInput.trim()) {
                    onChoiceSelect(customInput.trim())
                    setCustomInput('')
                  }
                }}
                className="px-2.5 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Send
              </button>
            </div>
          )}
        </div>
      )}
      </div>
      {msg.role === 'user' && (
        <User className="h-5 w-5 text-blue-500 shrink-0 mt-1" />
      )}
    </div>
  )
}
