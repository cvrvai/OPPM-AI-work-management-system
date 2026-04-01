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
  TrendingUp,
  ArrowRight,
  Shield,
  Target,
  Loader2,
} from 'lucide-react'
import { cn, getProgressColor } from '@/lib/utils'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

const EMPTY_CHART = [
  { day: 'Mon', commits: 0, quality: 0 },
  { day: 'Tue', commits: 0, quality: 0 },
  { day: 'Wed', commits: 0, quality: 0 },
  { day: 'Thu', commits: 0, quality: 0 },
  { day: 'Fri', commits: 0, quality: 0 },
  { day: 'Sat', commits: 0, quality: 0 },
  { day: 'Sun', commits: 0, quality: 0 },
]

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  label: string
  value: string | number
  icon: React.ElementType
  color: string
  subtitle?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-text-secondary">{label}</p>
          <p className="mt-1 text-2xl font-bold text-text">{value}</p>
          {subtitle && <p className="mt-0.5 text-xs text-text-secondary">{subtitle}</p>}
        </div>
        <div className={cn('rounded-lg p-2.5', color)}>
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
    </div>
  )
}

export function Dashboard() {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  useChatContext('workspace')

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats', ws?.id],
    queryFn: () => ws ? api.get<DashboardStats>(`${wsPath}/dashboard/stats`) : api.get<DashboardStats>('/dashboard/stats'),
  })

  const { data: recentAnalyses } = useQuery({
    queryKey: ['recent-analyses', ws?.id],
    queryFn: () => ws ? api.get<CommitAnalysis[]>(`${wsPath}/git/recent-analyses`) : api.get<CommitAnalysis[]>('/dashboard/recent-analyses'),
  })

  const s = stats || { total_projects: 0, active_projects: 0, total_tasks: 0, completed_tasks: 0, total_commits_today: 0, avg_quality_score: 0, avg_alignment_score: 0 }
  const analyses = recentAnalyses || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Dashboard</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Real-time overview of your OPPM projects and AI analysis
          </p>
        </div>
        <Link
          to="/projects"
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-dark transition-colors"
        >
          View Projects <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      {/* Stats Grid */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Projects"
          value={s.active_projects}
          subtitle={`${s.total_projects} total`}
          icon={FolderKanban}
          color="bg-primary"
        />
        <StatCard
          label="Tasks Completed"
          value={`${s.completed_tasks}/${s.total_tasks}`}
          subtitle={`${Math.round((s.completed_tasks / Math.max(s.total_tasks, 1)) * 100)}% done`}
          icon={CheckCircle2}
          color="bg-accent"
        />
        <StatCard
          label="Commits Today"
          value={s.total_commits_today}
          icon={GitCommitHorizontal}
          color="bg-violet-500"
        />
        <StatCard
          label="Avg Quality Score"
          value={`${s.avg_quality_score}%`}
          subtitle={`Alignment: ${s.avg_alignment_score}%`}
          icon={Shield}
          color="bg-amber-500"
        />
      </div>
      )}

      {/* Charts + Recent Activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Chart */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-text mb-4">Weekly Activity</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={EMPTY_CHART}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="commits"
                  stroke="#1a56db"
                  fill="#1a56db"
                  fillOpacity={0.1}
                  name="Commits"
                />
                <Area
                  type="monotone"
                  dataKey="quality"
                  stroke="#10b981"
                  fill="#10b981"
                  fillOpacity={0.08}
                  name="Quality %"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent AI Analysis */}
        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text">Recent AI Analysis</h2>
            <Link to="/commits" className="text-xs text-primary hover:underline">
              View all
            </Link>
          </div>
          <div className="space-y-3">
            {analyses.length === 0 ? (
              <p className="text-sm text-text-secondary text-center py-8">
                No AI analyses yet. Push commits to a linked repo to get started.
              </p>
            ) : (
              analyses.map((analysis) => (
                <div
                  key={analysis.id}
                  className="rounded-lg border border-border p-3 space-y-2"
                >
                  <p className="text-sm font-medium text-text line-clamp-2">
                    {analysis.summary}
                  </p>
                  <div className="flex items-center gap-3 text-xs text-text-secondary">
                    <span className="flex items-center gap-1">
                      <Target className="h-3 w-3" />
                      <span className={getProgressColor(analysis.task_alignment_score)}>
                        {analysis.task_alignment_score}%
                      </span>
                    </span>
                    <span className="flex items-center gap-1">
                      <Shield className="h-3 w-3" />
                      <span className={getProgressColor(analysis.code_quality_score)}>
                        {analysis.code_quality_score}%
                      </span>
                    </span>
                    <span className="flex items-center gap-1">
                      <TrendingUp className="h-3 w-3" />
                      +{analysis.progress_delta}%
                    </span>
                  </div>
                  <p className="text-[10px] text-text-secondary/60">{analysis.ai_model}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
