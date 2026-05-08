import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { getInitials, formatRelativeTime, cn } from '@/lib/utils'
import type { Notification } from '@/types'
import {
  Bell,
  CheckCheck,
  Info,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Cpu,
  GitCommitHorizontal,
  ListChecks,
  Menu,
  X,
} from 'lucide-react'

const typeIcons: Record<string, React.ElementType> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
  ai_analysis: Cpu,
  commit: GitCommitHorizontal,
  task_update: ListChecks,
}

const typeColors: Record<string, string> = {
  info: 'text-blue-500 bg-blue-50',
  success: 'text-emerald-500 bg-emerald-50',
  warning: 'text-amber-500 bg-amber-50',
  error: 'text-red-500 bg-red-50',
  ai_analysis: 'text-violet-500 bg-violet-50',
  commit: 'text-indigo-500 bg-indigo-50',
  task_update: 'text-cyan-500 bg-cyan-50',
}

export function Header({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const user = useAuthStore((s) => s.user)
  const email = user?.email || 'User'
  const name = user?.full_name || user?.user_metadata?.full_name || email.split('@')[0]
  const [showNotifs, setShowNotifs] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => api.get<{ count: number }>('/v1/notifications/unread-count'),
    refetchInterval: 30000,
  })

  const { data: notifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<Notification[]>('/v1/notifications?limit=20'),
    enabled: showNotifs,
  })

  const markRead = useMutation({
    mutationFn: (id: string) => api.put(`/v1/notifications/${id}/read`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })

  const markAllRead = useMutation({
    mutationFn: () => api.put('/v1/notifications/read-all', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })

  const deleteNotif = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/notifications/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })

  const unreadCount = unreadData?.count || 0
  const notifList = notifications || []

  // Close panel on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowNotifs(false)
      }
    }
    if (showNotifs) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showNotifs])

  const handleNotifClick = (notif: Notification) => {
    if (!notif.is_read) markRead.mutate(notif.id)
    if (notif.link) {
      navigate(notif.link)
      setShowNotifs(false)
    }
  }

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-border bg-white/90 px-4 backdrop-blur-sm sm:px-6">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="rounded-md p-1.5 text-text-secondary transition-colors hover:bg-surface-alt hover:text-text"
          title="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Notification Bell */}
        <div className="relative" ref={panelRef}>
          <button
            onClick={() => setShowNotifs(!showNotifs)}
            className="relative rounded-md p-1.5 text-text-secondary hover:bg-surface-alt transition-colors"
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute right-0.5 top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-danger text-[9px] font-bold text-white">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {/* Notification Panel */}
          {showNotifs && (
            <div className="absolute right-0 top-full mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-lg border border-border bg-white shadow-md">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
                <h3 className="text-sm font-semibold text-text">Notifications</h3>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllRead.mutate()}
                    className="flex items-center gap-1 text-xs text-text-secondary hover:text-text"
                  >
                    <CheckCheck className="h-3 w-3" /> Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-96 overflow-y-auto">
                {notifList.length === 0 ? (
                  <div className="px-4 py-8 text-center">
                    <Bell className="h-8 w-8 text-text-secondary/30 mx-auto mb-2" />
                    <p className="text-sm text-text-secondary">No notifications yet</p>
                  </div>
                ) : (
                  notifList.map((notif) => {
                    const Icon = typeIcons[notif.type] || Info
                    const colorClass = typeColors[notif.type] || typeColors.info
                    return (
                      <div
                        key={notif.id}
                        onClick={() => handleNotifClick(notif)}
                        className={cn(
                          'flex items-start gap-3 px-4 py-3 border-b border-border cursor-pointer hover:bg-surface-alt/50 transition-colors',
                          !notif.is_read && 'bg-primary/3'
                        )}
                      >
                        <div className={cn('rounded-lg p-1.5 mt-0.5 shrink-0', colorClass)}>
                          <Icon className="h-3.5 w-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className={cn('text-sm line-clamp-1', !notif.is_read ? 'font-semibold text-text' : 'text-text-secondary')}>
                              {notif.title}
                            </p>
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteNotif.mutate(notif.id) }}
                              className="shrink-0 text-text-secondary/40 hover:text-danger"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                          {notif.message && (
                            <p className="text-xs text-text-secondary line-clamp-2 mt-0.5">{notif.message}</p>
                          )}
                          <p className="text-[10px] text-text-secondary/60 mt-1">
                            {formatRelativeTime(notif.created_at)}
                          </p>
                        </div>
                        {!notif.is_read && (
                          <span className="h-2 w-2 rounded-full bg-primary shrink-0 mt-2" />
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* User */}
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-alt text-text text-xs font-semibold border border-border">
            {getInitials(name)}
          </div>
          <span className="hidden text-sm font-medium text-text sm:block">{name}</span>
        </div>
      </div>
    </header>
  )
}
