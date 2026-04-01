import { create } from 'zustand'

interface ChatMessage {
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
}

interface ChatState {
  isOpen: boolean
  messages: ChatMessage[]
  contextType: 'workspace' | 'project'
  projectId: string | null
  projectTitle: string | null
  unreadCount: number

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
  incrementUnread: () => void
  resetUnread: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  isOpen: false,
  messages: [],
  contextType: 'workspace',
  projectId: null,
  projectTitle: null,
  unreadCount: 0,

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
    // Clear messages when context changes between workspace/project or different projects
    const contextChanged =
      ctx.type !== state.contextType || newProjectId !== state.projectId
    set({
      contextType: ctx.type,
      projectId: newProjectId,
      projectTitle: ctx.projectTitle ?? null,
      ...(contextChanged ? { messages: [], unreadCount: 0 } : {}),
    })
  },

  addMessage: (msg) => {
    set((s) => ({
      messages: [...s.messages, msg],
      unreadCount: !s.isOpen && msg.role === 'assistant' ? s.unreadCount + 1 : s.unreadCount,
    }))
  },

  setMessages: (msgs) => set({ messages: msgs }),
  clearMessages: () => set({ messages: [], unreadCount: 0 }),
  incrementUnread: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),
  resetUnread: () => set({ unreadCount: 0 }),
}))
