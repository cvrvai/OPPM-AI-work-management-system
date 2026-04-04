import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { ChatFAB } from '@/components/ChatFAB'
import { ChatPanel } from '@/components/ChatPanel'

export function Layout() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(() => {
    if (typeof window === 'undefined') return true
    const storedValue = window.localStorage.getItem('layout:desktop-sidebar-open')
    return storedValue ? storedValue === 'true' : true
  })

  useEffect(() => {
    window.localStorage.setItem('layout:desktop-sidebar-open', String(isDesktopSidebarOpen))
  }, [isDesktopSidebarOpen])

  const handleToggleSidebar = () => {
    if (typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches) {
      setIsDesktopSidebarOpen((open) => !open)
      return
    }

    setIsMobileSidebarOpen((open) => !open)
  }

  return (
    <div className="min-h-screen bg-surface-alt">
      <Sidebar
        isMobileOpen={isMobileSidebarOpen}
        isDesktopOpen={isDesktopSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        onToggleDesktop={() => setIsDesktopSidebarOpen((open) => !open)}
      />
      <div className={isDesktopSidebarOpen ? 'min-h-screen transition-[padding] duration-200 lg:pl-60' : 'min-h-screen transition-[padding] duration-200 lg:pl-0'}>
        <Header onToggleSidebar={handleToggleSidebar} />
        <main className="p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
      <ChatFAB />
      <ChatPanel />
    </div>
  )
}
