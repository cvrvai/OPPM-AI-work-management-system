import { useEffect } from 'react'
import { useChatStore } from '@/stores/chatStore'

/**
 * Sets the chat context for the current page.
 * Call at the top of each page component.
 *
 * - Project pages: useChatContext('project', projectId, projectTitle)
 * - Non-project pages: useChatContext('workspace')
 */
export function useChatContext(
  type: 'workspace' | 'project',
  projectId?: string | null,
  projectTitle?: string | null,
) {
  const setContext = useChatStore((s) => s.setContext)

  useEffect(() => {
    setContext({ type, projectId, projectTitle })
  }, [type, projectId, projectTitle, setContext])
}
