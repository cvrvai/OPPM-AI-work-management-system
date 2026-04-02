import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatContext } from '@/hooks/useChatContext'
import type { DashboardStats, CommitAnalysis } from '@/types'
import { Link } from 'react-router-dom'
import {
  FolderKanban,
  CheckCircle2,
  GitCommitHorizontal,
  Shield,
  Target,
  TrendingUp,
  ArrowRight,
  BarChart2,
  GitBranch,
} from 'lucide-react'
import { cn, getProgressColor, getStatusColor } from '@/lib/utils'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { Skeleton } from '@/components/Skeleton'

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon: Icon,
  borderColor,
  iconBg,
  subtitle,
}: {
  label: string
  value: string | number
  icon: React.ElementType
  borderColor: string
  iconBg: string
  subtitle?: string
}) {
  return (
    <div className={cn('rounded-xl border border-border bg-white p-5 shadow-sm border-l-4', borderColor)}>
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">{label}</p>
          <p className="mt-1.5 text-3xl font-bold text-text leading-none">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-text-secondary">{subtitle}</p>}
        </div>
        <div className={cn('ml-3 flex-shrink-0 rounded-xl p-2.5', iconBg)}>
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
    </div>
  )
}

function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-white p-5 shadow-sm border-l-4 border-l-slate-200">
      <div className="flex items-start justify-between">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-3 w-20" />
        </div>
        <Skeleton className="ml-3 h-10 w-10 rounded-xl" />
      </div>
    </div>
  )
}

// ── Status bar colour per project status ──────────────────────────────────────

function barFill(status: string): string {
  switch (status) {
    case 'completed': return '#10b981'
    case 'in_progress': return '#1a56db'
    case 'planning': return '#f59e0b'
    case 'on_hold': return '#94a3b8'
    case 'cancelled': return '#ef4444'
    default: return '#1a56db'
  }
}

// ── Custom tooltip for the bar chart ─────────────────────────────────────────

function ProjectTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { title: string; progress: number; status: string } }> }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-border bg-white p-2.5 shadow-md text-xs">
      <p className="font-semibold text-text mb-1 max-w-[140px] truncate">{d.title}</p>
      <p className="text-text-secondary">Progress: <span className="font-medium text-text">{d.progress}%</span></p>
      <span className={cn('mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium', getStatusColor(d.status))}>
        {d.status.replace('_', ' ')}
      </span>
    </div>
  )
}

// ── Score Pill ────────────────────────────────────────────────────────────────

function ScorePill({ value, label }: { value: number; label: string }) {
  const bg =
    value >= 80 ? 'bg-emerald-100 text-emerald-700' :
    value >= 60 ? 'bg-blue-100 text-blue-700' :
    value >= 40 ? 'bg-amber-100 text-amber-700' :
    'bg-red-100 text-red-700'
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold', bg)}>
      {label}: {value}%
    </span>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export function Dashboard() {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  useChatContext('workspace')

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats', ws?.id],
    queryFn: () =>
      ws
        ? api.get<DashboardStats>(`${wsPath}/dashboard/stats`)
        : api.get<DashboardStats>('/dashboard/stats'),
  })

  const { data: recentAnalyses, isLoading: analysesLoading } = useQuery({
    queryKey: ['recent-analyses', ws?.id],
    queryFn: () =>
      ws
        ? api.get<CommitAnalysis[]>(`${wsPath}/git/recent-analyses`)
        : api.get<CommitAnalysis[]>('/dashboard/recent-analyses'),
  })

  const s = stats ?? {
    total_projects: 0,
    active_projects: 0,
    total_tasks: 0,
    completed_tasks: 0,
    total_commits_today: 0,
    avg_quality_score: 0,
    avg_alignment_score: 0,
    project_progress: [],
  }
  const analyses = recentAnalyses ?? []
  const taskPct = s.total_tasks > 0 ? Math.round((s.completed_tasks / s.total_tasks) * 100) : 0

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Dashboard</h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            Real-time overview of{ws ? ` ${ws.name}` : ' your'} OPPM projects and AI analysis
          </p>
        </div>
        <Link
          to="/projects"
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          View Projects <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard
              label="Active Projects"
              value={s.active_projects}
              subtitle={`${s.total_projects} total`}
              icon={FolderKanban}
              borderColor="border-l-primary"
              iconBg="bg-primary"
            />
            <StatCard
              label="Tasks Completed"
              value={`${taskPct}%`}
              subtitle={`${s.completed_tasks} of ${s.total_tasks} tasks`}
              icon={CheckCircle2}
              borderColor="border-l-emerald-500"
              iconBg="bg-accent"
            />
            <StatCard
              label="Commits Today"
              value={s.total_commits_today}
              icon={GitCommitHorizontal}
              borderColor="border-l-violet-500"
              iconBg="bg-violet-500"
            />
            <StatCard
              label="Avg Quality"
              value={`${s.avg_quality_score}%`}
              subtitle={`Alignment: ${s.avg_alignment_score}%`}
              icon={Shield}
              borderColor="border-l-amber-500"
              iconBg="bg-amber-500"
            />
          </>
        )}
      </div>

      {/* ── Charts Row ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

        {/* Project Progress Bar Chart */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold text-text">Project Progress</h2>
            {!statsLoading && s.project_progress.length > 0 && (
              <span className="ml-auto text-xs text-text-secondary">{s.project_progress.length} projects</span>
            )}
          </div>

          {statsLoading ? (
            <div className="space-y-3 pt-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-[200px] w-full rounded-lg" />
            </div>
          ) : s.project_progress.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center gap-2 text-text-secondary">
              <FolderKanban className="h-10 w-10 opacity-25" />
              <p className="text-sm font-medium">No projects yet</p>
              <p className="text-xs">Create a project to see its progress here.</p>
            </div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={s.project_progress}
                  margin={{ top: 4, right: 8, left: -16, bottom: 4 }}
                  barSize={s.project_progress.length > 8 ? 16 : 28}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="title"
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    tickLine={false}
                    axisLine={false}
                    interval={0}
                    tickFormatter={(v: string) => v.length > 10 ? v.slice(0, 10) + '…' : v}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tickFormatter={(v: number) => `${v}%`}
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip content={<ProjectTooltip />} cursor={{ fill: '#f1f5f9' }} />
                  <Bar dataKey="progress" radius={[4, 4, 0, 0]}>
                    {s.project_progress.map((entry, i) => (
                      <Cell key={i} fill={barFill(entry.status)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Legend */}
          {!statsLoading && s.project_progress.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
              {[
                { label: 'In Progress', color: '#1a56db' },
                { label: 'Planning', color: '#f59e0b' },
                { label: 'Completed', color: '#10b981' },
                { label: 'On Hold', color: '#94a3b8' },
              ].map((l) => (
                <span key={l.label} className="flex items-center gap-1.5 text-[11px] text-text-secondary">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: l.color }} />
                  {l.label}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Recent AI Analysis */}
        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold text-text">Recent AI Analysis</h2>
            </div>
            <Link to="/commits" className="text-xs font-medium text-primary hover:underline">
              View all
            </Link>
          </div>

          {analysesLoading ? (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="space-y-2 rounded-lg border border-border p-3">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                  <div className="flex gap-2">
                    <Skeleton className="h-5 w-20 rounded-full" />
                    <Skeleton className="h-5 w-20 rounded-full" />
                  </div>
                </div>
              ))}
            </div>
          ) : analyses.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center gap-2 text-text-secondary">
              <GitCommitHorizontal className="h-10 w-10 opacity-25" />
              <p className="text-sm font-medium">No analyses yet</p>
              <p className="text-xs text-center">Push commits to a linked repo to get started.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {analyses.map((analysis) => (
                <div
                  key={analysis.id}
                  className="rounded-lg border border-border p-3 space-y-2 hover:border-primary/30 transition-colors"
                >
                  <p className="text-sm font-medium text-text line-clamp-2 leading-snug">
                    {analysis.summary}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <ScorePill value={analysis.task_alignment_score} label="Alignment" />
                    <ScorePill value={analysis.code_quality_score} label="Quality" />
                    {analysis.progress_delta > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-semibold text-purple-700">
                        <TrendingUp className="h-2.5 w-2.5" />
                        +{analysis.progress_delta}%
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-text-secondary/60">{analysis.ai_model}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Project list (quick overview) ── */}
      {!statsLoading && s.project_progress.length > 0 && (
        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold text-text">All Projects</h2>
            </div>
            <Link to="/projects" className="text-xs font-medium text-primary hover:underline">
              Manage
            </Link>
          </div>
          <div className="space-y-3">
            {s.project_progress.map((p) => (
              <div key={p.project_id} className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <Link
                      to={`/projects/${p.project_id}`}
                      className="truncate text-sm font-medium text-text hover:text-primary transition-colors"
                    >
                      {p.title}
                    </Link>
                    <span className="flex-shrink-0 text-xs font-semibold text-text-secondary">
                      {p.progress}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${p.progress}%`, background: barFill(p.status) }}
                    />
                  </div>
                </div>
                <span className={cn('flex-shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-medium', getStatusColor(p.status))}>
                  {p.status.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

