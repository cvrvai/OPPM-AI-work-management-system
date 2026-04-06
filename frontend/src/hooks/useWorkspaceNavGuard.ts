import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspaceStore } from '@/stores/workspaceStore'

/**
 * Redirects to `to` whenever the active workspace changes.
 * Apply this in any project-scoped page (ProjectDetail, OPPMView, etc.)
 * so that switching workspace never leaves the user on a stale project URL
 * that would fire cross-workspace 404s.
 */
export function useWorkspaceNavGuard(to = '/projects') {
  const wsId = useWorkspaceStore((s) => s.currentWorkspace?.id)
  const navigate = useNavigate()
  const mountedWsId = useRef(wsId)

  useEffect(() => {
    if (wsId !== undefined && wsId !== mountedWsId.current) {
      navigate(to, { replace: true })
    }
  }, [wsId, navigate, to])
}
