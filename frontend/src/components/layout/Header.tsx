import { useAuthStore } from '@/stores/authStore'
import { getInitials } from '@/lib/utils'
import { Bell } from 'lucide-react'

export function Header() {
  const user = useAuthStore((s) => s.user)
  const email = user?.email || 'User'
  const name = user?.user_metadata?.full_name || email.split('@')[0]

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-white/80 backdrop-blur-sm px-6">
      <div />
      <div className="flex items-center gap-4">
        <button className="relative rounded-lg p-2 text-text-secondary hover:bg-surface-alt transition-colors">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-danger" />
        </button>
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white text-xs font-semibold">
            {getInitials(name)}
          </div>
          <span className="text-sm font-medium text-text">{name}</span>
        </div>
      </div>
    </header>
  )
}
