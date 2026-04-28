const API_BASE = import.meta.env.VITE_API_URL || '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...options.headers as Record<string, string>,
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  // Auto-refresh on 401 and retry once
  if (res.status === 401) {
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
        const retryHeaders: Record<string, string> = {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${data.access_token}`,
          ...options.headers as Record<string, string>,
        }
        const retry = await fetch(`${API_BASE}${path}`, {
          ...options,
          headers: retryHeaders,
        })
        if (!retry.ok) {
          const error = await retry.json().catch(() => ({ detail: retry.statusText }))
          throw new ApiError(retry.status, error.detail || 'Request failed')
        }
        return retry.json()
      }
    }
    // Refresh failed — clear tokens
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(401, error.detail || 'Request failed')
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, error.detail || 'Request failed')
  }
  return res.json()
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...options.headers as Record<string, string>,
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (res.status === 401) {
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
        const retryHeaders: Record<string, string> = {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${data.access_token}`,
          ...options.headers as Record<string, string>,
        }
        const retry = await fetch(`${API_BASE}${path}`, {
          ...options,
          headers: retryHeaders,
        })
        if (!retry.ok) {
          const error = await retry.json().catch(() => ({ detail: retry.statusText }))
          throw new ApiError(retry.status, error.detail || 'Request failed')
        }
        return retry.blob()
      }
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(401, error.detail || 'Request failed')
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, error.detail || 'Request failed')
  }
  return res.blob()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  getBlob: (path: string) => requestBlob(path),
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data) }),
  put: <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(data) }),
  patch: <T>(path: string, data: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  /**
   * Multipart/form-data POST.
   * Do NOT set Content-Type manually — the browser must set it so the
   * multipart boundary is included automatically.
   */
  postFormData: async <T>(path: string, form: FormData): Promise<T> => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: form,
    })
    if (res.status === 401) {
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
          if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
          const retry = await fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: form,
          })
          if (!retry.ok) {
            const err = await retry.json().catch(() => ({ detail: retry.statusText }))
            throw new ApiError(retry.status, err.detail || 'Request failed')
          }
          return retry.json()
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(401, err.detail || 'Unauthorized')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, err.detail || 'Request failed')
    }
    return res.json()
  },
}

export interface FileParseResult {
  filename: string
  content_type: string
  extracted_text: string
  truncated: boolean
  error: string | null
}

export async function parseFile(workspaceId: string, file: File): Promise<FileParseResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/v1/workspaces/${workspaceId}/ai/parse-file`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, err.detail || 'File parse failed')
  }
  return res.json()
}
