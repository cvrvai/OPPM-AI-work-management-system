import { NavLink, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { WorkspaceSelector } from '@/components/features/WorkspaceSelector'
import {
  LayoutDashboard,
  FolderKanban,
  GitCommitHorizontal,
  Settings,
  LogOut,
  Target,
  Users,
  X,
  Mail,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { MyInvite } from '@/types'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/projects', icon: FolderKanban, label: 'Projects' },
  { to: '/team', icon: Users, label: 'Team' },
  { to: '/commits', icon: GitCommitHorizontal, label: 'Commits' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

function InviteBadge() {
  const { data } = useQuery({
    queryKey: ['my-invites'],
    queryFn: () => api.get<MyInvite[]>('/v1/invites/my-invites'),
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: 1,
  })
  const count = (data ?? []).filter((i) => !i.is_expired).length
  if (!count) return null
  return (
    <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-white">
      {count}
    </span>
  )
}

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
          'fixed inset-y-0 left-0 z-40 flex w-[17.5rem] max-w-[85vw] flex-col bg-sidebar text-sidebar-text shadow-sm transition-transform duration-200 lg:w-60 lg:shadow-none border-r border-border',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full',
          isDesktopOpen ? 'lg:translate-x-0' : 'lg:-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center justify-between gap-2.5 border-b border-border px-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
              <Target className="h-4 w-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-text tracking-tight">OPPM AI</h1>
              <p className="text-[10px] text-text-secondary leading-none">Work Management</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onToggleDesktop}
            className="hidden rounded-md p-1.5 text-text-secondary transition-colors hover:bg-sidebar-hover lg:inline-flex"
            title={isDesktopOpen ? 'Hide sidebar' : 'Show sidebar'}
          >
            <X className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onCloseMobile}
            className="rounded-md p-1.5 text-text-secondary transition-colors hover:bg-sidebar-hover lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Workspace Selector */}
        <div className="border-b border-border">
          <WorkspaceSelector />
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-0.5 px-2 py-3">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-sidebar-active text-sidebar-active-text'
                    : 'text-sidebar-text hover:bg-sidebar-hover'
                )
              }
            >
              <Icon className="h-4 w-4 text-text-secondary" />
              {label}
            </NavLink>
          ))}
          {/* Invitations — with live badge */}
          <NavLink
            to="/invitations"
            onClick={onCloseMobile}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-active text-sidebar-active-text'
                  : 'text-sidebar-text hover:bg-sidebar-hover'
              )
            }
          >
            <Mail className="h-4.5 w-4.5" />
            Invitations
            <InviteBadge />
          </NavLink>
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-2">
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-sidebar-text transition-colors hover:bg-sidebar-hover"
          >
            <LogOut className="h-4 w-4 text-text-secondary" />
            Sign Out
          </button>
        </div>
      </aside>
    </>
  )
}
