import { create } from 'zustand'

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

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  isAuthenticated: false,

  getToken: () => localStorage.getItem('access_token'),

  initialize: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ user: null, isAuthenticated: false, loading: false })
      return
    }
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const user = await res.json()
        set({ user, isAuthenticated: true, loading: false })
      } else if (res.status === 401) {
        // Try refresh
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          })
          if (refreshRes.ok) {
            const data = await refreshRes.json()
            localStorage.setItem('access_token', data.access_token)
            if (data.refresh_token) {
              localStorage.setItem('refresh_token', data.refresh_token)
            }
            const retryRes = await fetch(`${API_BASE}/auth/me`, {
              headers: { Authorization: `Bearer ${data.access_token}` },
            })
            if (retryRes.ok) {
              const user = await retryRes.json()
              set({ user, isAuthenticated: true, loading: false })
              return
            }
          }
        }
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, isAuthenticated: false, loading: false })
      } else {
        set({ user: null, isAuthenticated: false, loading: false })
      }
    } catch {
      set({ user: null, isAuthenticated: false, loading: false })
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
    localStorage.setItem('access_token', data.access_token)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
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
      localStorage.setItem('access_token', data.access_token)
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token)
      }
    }
    if (data.user) {
      set({ user: data.user, isAuthenticated: true })
    }
  },

  signOut: async () => {
    const token = localStorage.getItem('access_token')
    await fetch(`${API_BASE}/auth/signout`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => {})
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, isAuthenticated: false })
  },

  refreshSession: async () => {
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      set({ user: null, isAuthenticated: false })
      return
    }
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (res.ok) {
      const data = await res.json()
      localStorage.setItem('access_token', data.access_token)
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token)
      }
    } else {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      set({ user: null, isAuthenticated: false })
    }
  },
}))

