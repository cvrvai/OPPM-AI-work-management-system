// Custom client configuration for @hey-api generated SDK
// Wires the generated client to use our fetchWithSessionRetry for auth + token refresh

import { createClient, createConfig } from '@/generated/workspace-api/client'
import { fetchWithSessionRetry } from '@/lib/api/sessionClient'
import type { ClientOptions } from '@/generated/workspace-api/types.gen'

const patchedFetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  let url: string
  if (input instanceof Request) {
    url = input.url
  } else if (typeof input === 'string') {
    url = input
  } else {
    url = input.toString()
  }
  // The generated SDK passes full URLs (baseUrl + path) to fetch.
  // fetchWithSessionRetry expects just the path (it prepends API_BASE).
  // Strip the origin and the /api base path so we pass only the route path.
  try {
    const parsed = new URL(url)
    url = parsed.pathname + parsed.search + parsed.hash
  } catch {
    // url is already a relative path — nothing to do
  }
  if (url.startsWith('/api')) {
    url = url.substring(4)
  }
  return fetchWithSessionRetry(url, init)
}

export const workspaceClient = createClient(
  createConfig<ClientOptions>({
    baseUrl: '',
    fetch: patchedFetch,
  })
)
