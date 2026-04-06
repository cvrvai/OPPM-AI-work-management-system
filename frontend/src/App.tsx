import { useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Layout } from '@/components/layout/Layout'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { Projects } from '@/pages/Projects'
import { ProjectDetail } from '@/pages/ProjectDetail'
import { OPPMView } from '@/pages/OPPMView'
import { Commits } from '@/pages/Commits'
import { Settings } from '@/pages/Settings'
import { AcceptInvite } from '@/pages/AcceptInvite'
import { Team } from '@/pages/Team'
import { Invitations } from '@/pages/Invitations'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 3,
      // Exponential backoff: 1s, 2s, 4s — handles transient 503s on service startup
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
      refetchOnWindowFocus: true,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuthStore()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  const initialize = useAuthStore((s) => s.initialize)
  const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces)
  const initRef = useRef(false)

  useEffect(() => {
    // Guard against React StrictMode double-invocation to avoid duplicate API calls
    if (initRef.current) return
    initRef.current = true
    initialize().then(() => {
      if (useAuthStore.getState().isAuthenticated) {
        return fetchWorkspaces()
      }
    })
  }, [initialize, fetchWorkspaces])

  // No global loading gate — public routes (login, accept-invite) render immediately.
  // ProtectedRoute handles the loading spinner only for authenticated areas.
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/invites/:token" element={<AcceptInvite />} />
          <Route path="/invite/accept/:token" element={<AcceptInvite />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="projects" element={<Projects />} />
            <Route path="projects/:id" element={<ProjectDetail />} />
            <Route path="projects/:id/oppm" element={<OPPMView />} />
            <Route path="team" element={<Team />} />
            <Route path="invitations" element={<Invitations />} />
            <Route path="commits" element={<Commits />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
