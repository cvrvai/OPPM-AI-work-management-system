import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { ChatFAB } from '@/components/features/ChatFAB'
import { ChatPanel } from '@/components/features/ChatPanel'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { UpdateToast } from '@/components/features/UpdateToast'
import { ToastContainer } from '@/components/features/ToastContainer'

export function Layout() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(() => {
    if (typeof window === 'undefined') return true
    const storedValue = window.localStorage.getItem('layout:desktop-sidebar-open')
    return storedValue ? storedValue === 'true' : true
  })
  const location = useLocation()
  const isOppmView = location.pathname.includes('/oppm')

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
    <div className="min-h-screen bg-white">
      <Sidebar
        isMobileOpen={isMobileSidebarOpen}
        isDesktopOpen={isDesktopSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        onToggleDesktop={() => setIsDesktopSidebarOpen((open) => !open)}
      />
      <div className={isDesktopSidebarOpen ? 'min-h-screen transition-[padding] duration-200 lg:pl-60' : 'min-h-screen transition-[padding] duration-200 lg:pl-0'}>
        <Header onToggleSidebar={handleToggleSidebar} />
        <main className={isOppmView ? 'p-0 h-screen overflow-hidden' : 'p-6 sm:p-8 max-w-6xl mx-auto'}>
          <Outlet />
        </main>
      </div>
      <ChatFAB />
      <ErrorBoundary context="chat-panel">
        <ChatPanel />
      </ErrorBoundary>
      <UpdateToast />
      <ToastContainer />
    </div>
  )
}
