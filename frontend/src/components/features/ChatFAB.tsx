/**
 * ChatFAB — Floating Action Button for AI Chat.
 * Fixed bottom-right, visible on all authenticated pages.
 */

import { useEffect } from 'react'
import { MessageCircle, X } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { cn } from '@/lib/utils'

export function ChatFAB() {
  const isOpen = useChatStore((s) => s.isOpen)
  const toggle = useChatStore((s) => s.toggle)
  const unreadCount = useChatStore((s) => s.unreadCount)

  // Keyboard shortcut: Ctrl+Shift+A
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [toggle])

  return (
    <button
      onClick={toggle}
      className={cn(
        'fixed bottom-6 right-6 z-50 flex items-center justify-center',
        'h-12 w-12 rounded-full shadow-md transition-all duration-200',
        'hover:scale-105 active:scale-95',
        isOpen
          ? 'bg-text hover:bg-primary-dark text-white'
          : 'bg-primary hover:bg-primary-dark text-white',
      )}
      title="AI Chat (Ctrl+Shift+A)"
    >
      {isOpen ? (
        <X className="h-6 w-6" />
      ) : (
        <>
          <MessageCircle className="h-6 w-6" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white ring-2 ring-white">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </>
      )}
    </button>
  )
}
