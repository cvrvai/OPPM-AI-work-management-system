import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { WorkspaceSelector } from '@/components/workspace/WorkspaceSelector'
import {
  LayoutDashboard,
  FolderKanban,
  GitCommitHorizontal,
  Settings,
  LogOut,
  Target,
  Users,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/projects', icon: FolderKanban, label: 'Projects' },
  { to: '/team', icon: Users, label: 'Team' },
  { to: '/commits', icon: GitCommitHorizontal, label: 'Commits' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar({
  isMobileOpen,
  isDesktopOpen,
  onCloseMobile,
  onToggleDesktop,
}: {
  isMobileOpen: boolean
  isDesktopOpen: boolean
  onCloseMobile: () => void
  onToggleDesktop: () => void
}) {
  const signOut = useAuthStore((s) => s.signOut)
  const navigate = useNavigate()

  const handleSignOut = async () => {
    onCloseMobile()
    await signOut()
    navigate('/login')
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close navigation"
        onClick={onCloseMobile}
        className={cn(
          'fixed inset-0 z-30 bg-slate-950/45 backdrop-blur-sm transition-opacity lg:hidden',
          isMobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        )}
      />

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-[17.5rem] max-w-[85vw] flex-col bg-sidebar text-sidebar-text shadow-2xl transition-transform duration-200 lg:w-60 lg:shadow-none',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full',
          isDesktopOpen ? 'lg:translate-x-0' : 'lg:-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between gap-2.5 border-b border-white/10 px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Target className="h-4.5 w-4.5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-tight">OPPM AI</h1>
              <p className="text-[10px] text-sidebar-text/60 leading-none">Work Management</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onToggleDesktop}
            className="hidden rounded-lg p-2 text-sidebar-text/70 transition-colors hover:bg-sidebar-hover hover:text-white lg:inline-flex"
            title={isDesktopOpen ? 'Hide sidebar' : 'Show sidebar'}
          >
            <X className="h-4.5 w-4.5" />
          </button>
          <button
            type="button"
            onClick={onCloseMobile}
            className="rounded-lg p-2 text-sidebar-text/70 transition-colors hover:bg-sidebar-hover hover:text-white lg:hidden"
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* Workspace Selector */}
        <div className="border-b border-white/10">
          <WorkspaceSelector />
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-sidebar-active text-white'
                    : 'text-sidebar-text hover:bg-sidebar-hover hover:text-white'
                )
              }
            >
              <Icon className="h-4.5 w-4.5" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-white/10 p-3">
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-text transition-colors hover:bg-sidebar-hover hover:text-white"
          >
            <LogOut className="h-4.5 w-4.5" />
            Sign Out
          </button>
        </div>
      </aside>
    </>
  )
}
