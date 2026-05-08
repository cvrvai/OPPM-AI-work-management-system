import { clearTokens, getAccessToken, getRefreshToken } from '@/lib/api/tokens'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export interface SessionTokens {
  access_token: string
  refresh_token?: string
}

export type SessionEvent =
  | { type: 'cleared' }
  | { type: 'updated'; accessToken: string }

type SessionListener = (event: SessionEvent) => void

const listeners = new Set<SessionListener>()

let inFlightRefresh: Promise<SessionTokens | null> | null = null

function notifySessionListeners(event: SessionEvent): void {
  listeners.forEach((listener) => listener(event))
}

function buildHeaders(headers: HeadersInit | undefined, accessToken: string | null): Headers {
  const mergedHeaders = new Headers(headers)
  if (accessToken) {
    mergedHeaders.set('Authorization', `Bearer ${accessToken}`)
  }
  return mergedHeaders
}

async function performRefresh(): Promise<SessionTokens | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    clearSession()
    return null
  }

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      if (response.status === 401) {
        // Refresh token is explicitly invalid or expired — log out
        clearSession()
      }
      // For 5xx / network errors keep tokens so the user can retry after services recover
      return null
    }

    const sessionTokens = await response.json() as SessionTokens
    persistSession(sessionTokens)
    return sessionTokens
  } catch {
    // Network error (service down during restart, etc.) — keep tokens, let the user retry
    return null
  }
}

export function subscribeToSessionEvents(listener: SessionListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function persistSession(sessionTokens: SessionTokens): void {
  localStorage.setItem('access_token', sessionTokens.access_token)
  if (sessionTokens.refresh_token) {
    localStorage.setItem('refresh_token', sessionTokens.refresh_token)
  }
  notifySessionListeners({ type: 'updated', accessToken: sessionTokens.access_token })
}

export function clearSession(): void {
  clearTokens()
  notifySessionListeners({ type: 'cleared' })
}

export async function refreshSessionTokens(): Promise<SessionTokens | null> {
  if (inFlightRefresh) {
    return inFlightRefresh
  }

  inFlightRefresh = performRefresh().finally(() => {
    inFlightRefresh = null
  })

  return inFlightRefresh
}

export async function fetchWithSessionRetry(path: string, options: RequestInit = {}): Promise<Response> {
  const executeFetch = (accessToken: string | null) => fetch(`${API_BASE}${path}`, {
    ...options,
    headers: buildHeaders(options.headers, accessToken),
  })

  let response = await executeFetch(getAccessToken())
  if (response.status !== 401) {
    return response
  }

  const refreshedSession = await refreshSessionTokens()
  if (!refreshedSession?.access_token) {
    return response
  }

  response = await executeFetch(refreshedSession.access_token)
  return response
}

export function hasStoredSession(): boolean {
  return !!(getAccessToken() || getRefreshToken())
}
