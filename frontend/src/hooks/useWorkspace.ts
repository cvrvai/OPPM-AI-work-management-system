import { useWorkspaceStore } from '@/stores/workspaceStore'

/**
 * Returns the current workspace ID.
 * Throws if no workspace is selected (should be caught by workspace gate in routing).
 */
export function useWorkspaceId(): string {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  if (!ws) throw new Error('No workspace selected')
  return ws.id
}

/**
 * Returns workspace-scoped API path prefix.
 * Usage: `${wsPath}/projects` → `/v1/workspaces/<id>/projects`
 */
export function useWsPath(): string {
  const wsId = useWorkspaceId()
  return `/v1/workspaces/${wsId}`
}
