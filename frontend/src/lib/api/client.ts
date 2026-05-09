import { fetchWithSessionRetry } from '@/lib/api/sessionClient'
import type { SheetAction, SheetActionsResponse } from '@/types'

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
  // Pydantic / FastAPI validation errors return { detail: [...] } arrays.
  const detail = error.detail
  let message: string
  if (Array.isArray(detail)) {
    message = detail
      .map((e: any) => {
        const loc = Array.isArray(e.loc) ? e.loc.join('.') : ''
        const msg = e.msg || e.message || JSON.stringify(e)
        return loc ? `${loc}: ${msg}` : msg
      })
      .join('; ')
  } else {
    message = detail || error.message || fallbackMessage
  }
  return new ApiError(response.status, message)
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
  get: <T>(path: string, options?: RequestInit) => request<T>(path, options),
  getBlob: (path: string, options?: RequestInit) => requestBlob(path, options),
  post: <T>(path: string, data: unknown, options?: RequestInit) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data), ...options }),
  put: <T>(path: string, data: unknown, options?: RequestInit) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(data), ...options }),
  patch: <T>(path: string, data: unknown, options?: RequestInit) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(data), ...options }),
  delete: <T>(path: string, options?: RequestInit) => request<T>(path, { method: 'DELETE', ...options }),

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

export async function executeSheetActions(
  workspaceId: string,
  projectId: string,
  actions: SheetAction[],
): Promise<SheetActionsResponse> {
  const response = await fetchWithSessionRetry(
    `/v1/workspaces/${workspaceId}/projects/${projectId}/oppm/google-sheet/actions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actions }),
    },
  )
  if (!response.ok) {
    throw await getApiError(response, 'Failed to execute sheet actions')
  }
  return response.json()
}

export async function getGoogleSheetSnapshot(
  workspaceId: string,
  projectId: string,
): Promise<{
  spreadsheet_id: string
  sheet_title: string
  max_row: number
  max_col: number
  merge_ranges: string[]
  cells: Array<{
    r: number
    c: number
    v?: string
    n?: string
    bg?: string
    b?: string
    bold?: boolean
    fs?: number
    fg?: string
  }>
  cell_count: number
}> {
  return api.get(`/v1/workspaces/${workspaceId}/projects/${projectId}/oppm/google-sheet/snapshot`)
}

export async function getOppmSheetPrompt(
  workspaceId: string,
): Promise<{ config_key: string; prompt: string; is_default: boolean }> {
  return api.get(`/v1/workspaces/${workspaceId}/ai-config/oppm-sheet-prompt`)
}

export async function updateOppmSheetPrompt(
  workspaceId: string,
  prompt: string,
): Promise<{ config_key: string; prompt: string; is_default: boolean }> {
  return api.put(`/api/v1/workspaces/${workspaceId}/ai-config/oppm-sheet-prompt`, { prompt })
}

export async function resetOppmSheetPrompt(
  workspaceId: string,
): Promise<{ config_key: string; prompt: string; is_default: boolean }> {
  return api.delete(`/api/v1/workspaces/${workspaceId}/ai-config/oppm-sheet-prompt`)
}
