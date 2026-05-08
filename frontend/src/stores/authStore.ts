import { create } from 'zustand'
import { getAccessToken, getRefreshToken } from '@/lib/api/tokens'
import {
  clearSession,
  fetchWithSessionRetry,
  hasStoredSession,
  persistSession,
  refreshSessionTokens,
  subscribeToSessionEvents,
} from '@/lib/api/sessionClient'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

interface User {
  id: string
  email: string
  full_name?: string
  role?: string
  created_at?: string
  last_sign_in_at?: string
  user_metadata?: {
    full_name?: string
  }
  app_metadata?: {
    provider?: string
  }
}

interface AuthState {
  user: User | null
  loading: boolean
  isAuthenticated: boolean
  initialize: () => Promise<void>
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
  getToken: () => string | null
}

async function fetchCurrentUser(): Promise<User | null> {
  const response = await fetchWithSessionRetry('/auth/me')
  if (!response.ok) {
    return null
  }

  return response.json() as Promise<User>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  isAuthenticated: false,

  getToken: () => getAccessToken(),

  initialize: async () => {
    if (!hasStoredSession()) {
      set({ user: null, isAuthenticated: false, loading: false })
      return
    }

    try {
      const user = await fetchCurrentUser()
      if (user) {
        set({ user, isAuthenticated: true, loading: false })
        return
      }

      // fetchCurrentUser returned null — check why.
      // If tokens are still in localStorage, sessionClient did NOT call clearSession,
      // meaning this was a transient network/server error (service restarting, etc.).
      // Keep the user authenticated so they can retry once services recover.
      if (hasStoredSession()) {
        set({ isAuthenticated: true, loading: false })
        return
      }

      // Tokens were cleared by sessionClient (401 from refresh) — actually invalid.
      set({ user: null, isAuthenticated: false, loading: false })
    } catch {
      // Unexpected error during init — if tokens are still present assume network issue.
      if (hasStoredSession()) {
        set({ isAuthenticated: true, loading: false })
      } else {
        set({ user: null, isAuthenticated: false, loading: false })
      }
    }
  },

  signIn: async (email, password) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(err.detail)
    }
    const data = await res.json()
    persistSession(data)
    set({ user: data.user, isAuthenticated: true })
  },

  signUp: async (email, password) => {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Signup failed' }))
      throw new Error(err.detail)
    }
    const data = await res.json()
    if (data.access_token) {
      persistSession(data)
    }
    if (data.user) {
      set({ user: data.user, isAuthenticated: true })
    }
  },

  signOut: async () => {
    const token = getAccessToken()
    await fetch(`${API_BASE}/auth/signout`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => {})
    clearSession()
    set({ user: null, isAuthenticated: false })
  },

  refreshSession: async () => {
    if (!getRefreshToken()) {
      set({ user: null, isAuthenticated: false })
      return
    }

    const sessionTokens = await refreshSessionTokens()
    if (!sessionTokens) {
      set({ user: null, isAuthenticated: false })
      return
    }

    const user = await fetchCurrentUser()
    if (!user) {
      clearSession()
      set({ user: null, isAuthenticated: false })
      return
    }

    set({ user, isAuthenticated: true })
  },
}))

subscribeToSessionEvents((event) => {
  if (event.type === 'cleared') {
    useAuthStore.setState({ user: null, isAuthenticated: false, loading: false })
  }
})

