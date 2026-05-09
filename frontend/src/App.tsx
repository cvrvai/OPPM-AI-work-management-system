import { useEffect, useRef, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { ApiError, api } from '@/lib/api'
import { hasStoredSession } from '@/lib/api/sessionClient'
import { lazyNamed } from '@/lib/utils/lazyNamed'
import { Layout } from '@/components/layout/Layout'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { SuspenseFallback } from '@/components/ui/SuspenseFallback'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'

const Projects = lazyNamed(() => import('@/pages/Projects'), 'Projects')
const ProjectDetail = lazyNamed(() => import('@/pages/ProjectDetail'), 'ProjectDetail')
const OPPMView = lazyNamed(() => import('@/pages/OPPMView'), 'OPPMView')
const AgileBoard = lazyNamed(() => import('@/pages/AgileBoard'), 'AgileBoard')
const WaterfallView = lazyNamed(() => import('@/pages/WaterfallView'), 'WaterfallView')
const Commits = lazyNamed(() => import('@/pages/Commits'), 'Commits')
const Settings = lazyNamed(() => import('@/pages/Settings'), 'Settings')
const AcceptInvite = lazyNamed(() => import('@/pages/AcceptInvite'), 'AcceptInvite')
const Team = lazyNamed(() => import('@/pages/Team'), 'Team')
const Invitations = lazyNamed(() => import('@/pages/Invitations'), 'Invitations')

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Disable window-focus refetch — causes jarring reloads when switching tabs/apps
      refetchOnWindowFocus: false,
      // Keep retry logic for transient errors
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
        return failureCount < 3
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
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

    // Parallel warm-start: if we have a cached workspace and tokens, prefetch
    // dashboard data immediately so the first paint feels instant.
    const cachedWs = useWorkspaceStore.getState().currentWorkspace
    if (cachedWs && hasStoredSession()) {
      queryClient.prefetchQuery({
        queryKey: ['dashboard-stats', cachedWs.id],
        queryFn: () => api.get(`/v1/workspaces/${cachedWs.id}/dashboard/stats`),
        staleTime: 30_000,
      })
      queryClient.prefetchQuery({
        queryKey: ['projects', cachedWs.id],
        queryFn: async () => {
          const res = await api.get<{ items: unknown[]; total: number }>(`/v1/workspaces/${cachedWs.id}/projects`)
          return res.items ?? []
        },
        staleTime: 30_000,
      })
    }

    // Auth init and workspace fetch can run in parallel when tokens exist.
    // We still chain them so that workspace fetch only happens for valid sessions,
    // but we kick off auth immediately and don't block on it.
    const authPromise = initialize()
    const workspacePromise = hasStoredSession()
      ? fetchWorkspaces()
      : Promise.resolve()

    Promise.all([authPromise, workspacePromise]).then(([_, __]) => {
      // After both settle, if auth ended up invalid but we optimistically
      // fetched workspaces, clear the stale prefetches.
      if (!useAuthStore.getState().isAuthenticated) {
        queryClient.clear()
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
          <Route path="/invites/:token" element={<Suspense fallback={<SuspenseFallback />}><AcceptInvite /></Suspense>} />
          <Route path="/invite/accept/:token" element={<Suspense fallback={<SuspenseFallback />}><AcceptInvite /></Suspense>} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <ErrorBoundary context="app-shell">
                  <Layout />
                </ErrorBoundary>
              </ProtectedRoute>
            }
          >
            <Route index element={<Suspense fallback={<SuspenseFallback />}><Dashboard /></Suspense>} />
            <Route path="projects" element={<Suspense fallback={<SuspenseFallback />}><Projects /></Suspense>} />
            <Route path="projects/:id" element={<Suspense fallback={<SuspenseFallback />}><ProjectDetail /></Suspense>} />
            <Route path="projects/:id/oppm" element={<Suspense fallback={<SuspenseFallback />}><OPPMView /></Suspense>} />
            <Route path="projects/:id/agile" element={<Suspense fallback={<SuspenseFallback />}><AgileBoard /></Suspense>} />
            <Route path="projects/:id/waterfall" element={<Suspense fallback={<SuspenseFallback />}><WaterfallView /></Suspense>} />
            <Route path="team" element={<Suspense fallback={<SuspenseFallback />}><Team /></Suspense>} />
            <Route path="invitations" element={<Suspense fallback={<SuspenseFallback />}><Invitations /></Suspense>} />
            <Route path="commits" element={<Suspense fallback={<SuspenseFallback />}><Commits /></Suspense>} />
            <Route path="settings" element={<Suspense fallback={<SuspenseFallback />}><Settings /></Suspense>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
