import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface FileAttachment {
  name: string
  /** text = extracted text content; image = data URL; binary = no content */
  type: 'text' | 'image' | 'binary'
  content: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: {
    tool: string
    input: Record<string, unknown>
    result: Record<string, unknown>
    success: boolean
    error?: string | null
  }[]
  updatedEntities?: string[]
  attachments?: FileAttachment[]
  lowConfidence?: boolean
}

export function getContextKey(
  type: 'workspace' | 'project',
  projectId: string | null,
): string {
  return type === 'project' && projectId ? `project:${projectId}` : 'workspace'
}

const MAX_HISTORY = 120

interface ChatState {
  isOpen: boolean
  messages: ChatMessage[]
  contextType: 'workspace' | 'project'
  projectId: string | null
  projectTitle: string | null
  unreadCount: number
  /** Persisted per-context message histories keyed by getContextKey() */
  contextHistories: Record<string, ChatMessage[]>

  toggle: () => void
  open: () => void
  close: () => void
  setContext: (ctx: {
    type: 'workspace' | 'project'
    projectId?: string | null
    projectTitle?: string | null
  }) => void
  addMessage: (msg: ChatMessage) => void
  setMessages: (msgs: ChatMessage[]) => void
  clearMessages: () => void
  clearContextHistory: (key: string) => void
  incrementUnread: () => void
  resetUnread: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      isOpen: false,
      messages: [],
      contextType: 'workspace',
      projectId: null,
      projectTitle: null,
      unreadCount: 0,
      contextHistories: {},

      toggle: () => {
        const wasOpen = get().isOpen
        set({ isOpen: !wasOpen })
        if (!wasOpen) set({ unreadCount: 0 })
      },

      open: () => set({ isOpen: true, unreadCount: 0 }),
      close: () => set({ isOpen: false }),

      setContext: (ctx) => {
        const state = get()
        const newProjectId = ctx.projectId ?? null
        const contextChanged =
          ctx.type !== state.contextType || newProjectId !== state.projectId

        if (!contextChanged) {
          set({ projectTitle: ctx.projectTitle ?? state.projectTitle })
          return
        }

        // Persist current messages before switching
        const currentKey = getContextKey(state.contextType, state.projectId)
        const histories = { ...state.contextHistories }
        if (state.messages.length > 0) {
          histories[currentKey] = state.messages.slice(-MAX_HISTORY)
        }

        // Restore history for the new context
        const newKey = getContextKey(ctx.type, newProjectId)
        const restored = histories[newKey] ?? []

        set({
          contextType: ctx.type,
          projectId: newProjectId,
          projectTitle: ctx.projectTitle ?? null,
          messages: restored,
          unreadCount: 0,
          contextHistories: histories,
        })
      },

      addMessage: (msg) => {
        set((s) => {
          const newMessages = [...s.messages, msg]
          const key = getContextKey(s.contextType, s.projectId)
          return {
            messages: newMessages,
            unreadCount:
              !s.isOpen && msg.role === 'assistant'
                ? s.unreadCount + 1
                : s.unreadCount,
            contextHistories: {
              ...s.contextHistories,
              [key]: newMessages.slice(-MAX_HISTORY),
            },
          }
        })
      },

      setMessages: (msgs) => set({ messages: msgs }),
      clearMessages: () => set({ messages: [], unreadCount: 0 }),

      clearContextHistory: (key) => {
        set((s) => {
          const histories = { ...s.contextHistories }
          delete histories[key]
          const isCurrentKey =
            key === getContextKey(s.contextType, s.projectId)
          return {
            contextHistories: histories,
            ...(isCurrentKey ? { messages: [], unreadCount: 0 } : {}),
          }
        })
      },

      incrementUnread: () =>
        set((s) => ({ unreadCount: s.unreadCount + 1 })),
      resetUnread: () => set({ unreadCount: 0 }),
    }),
    {
      name: 'oppm-chat-history',
      // Only persist conversation histories — not transient UI state
      partialize: (s) => ({ contextHistories: s.contextHistories }),
      // Restore messages for the active context after hydration from localStorage
      onRehydrateStorage: () => (state) => {
        if (state) {
          const key = getContextKey(state.contextType, state.projectId)
          const restored = state.contextHistories[key] ?? []
          if (restored.length > 0) {
            state.messages = restored
          }
        }
      },
    },
  ),
)
