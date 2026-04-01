import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { ChatFAB } from '@/components/ChatFAB'
import { ChatPanel } from '@/components/ChatPanel'

export function Layout() {
  return (
    <div className="min-h-screen bg-surface-alt">
      <Sidebar />
      <div className="ml-60">
        <Header />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
      <ChatFAB />
      <ChatPanel />
    </div>
  )
}
