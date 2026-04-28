import { fetchWithSessionRetry } from '@/lib/sessionClient'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getJsonHeaders(headers?: HeadersInit): Headers {
  const mergedHeaders = new Headers(headers)
  if (!mergedHeaders.has('Content-Type')) {
    mergedHeaders.set('Content-Type', 'application/json')
  }
  return mergedHeaders
}

async function getApiError(response: Response, fallbackMessage = 'Request failed'): Promise<ApiError> {
  const error = await response.json().catch(() => ({ detail: response.statusText }))
  return new ApiError(response.status, error.detail || fallbackMessage)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetchWithSessionRetry(path, {
    ...options,
    headers: getJsonHeaders(options.headers),
  })

  if (!response.ok) {
    throw await getApiError(response)
  }
  return response.json()
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const response = await fetchWithSessionRetry(path, {
    ...options,
    headers: getJsonHeaders(options.headers),
  })

  if (!response.ok) {
    throw await getApiError(response)
  }
  return response.blob()
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
    const response = await fetchWithSessionRetry(path, {
      method: 'POST',
      body: form,
    })

    if (!response.ok) {
      throw await getApiError(response, 'Unauthorized')
    }

    return response.json()
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
  const response = await fetchWithSessionRetry(`/v1/workspaces/${workspaceId}/ai/parse-file`, {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    throw await getApiError(response, 'File parse failed')
  }

  return response.json()
}
