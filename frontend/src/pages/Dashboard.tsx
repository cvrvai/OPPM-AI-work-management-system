import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
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

// Placeholder data for demo
const DEMO_STATS: DashboardStats = {
  total_projects: 3,
  active_projects: 2,
  total_tasks: 18,
  completed_tasks: 7,
  total_commits_today: 5,
  avg_quality_score: 82,
  avg_alignment_score: 76,
}

const DEMO_CHART = [
  { day: 'Mon', commits: 4, quality: 78 },
  { day: 'Tue', commits: 7, quality: 82 },
  { day: 'Wed', commits: 3, quality: 85 },
  { day: 'Thu', commits: 9, quality: 79 },
  { day: 'Fri', commits: 6, quality: 88 },
  { day: 'Sat', commits: 2, quality: 90 },
  { day: 'Sun', commits: 5, quality: 84 },
]

const DEMO_RECENT: CommitAnalysis[] = [
  {
    id: '1',
    commit_event_id: '1',
    ai_model: 'kimi-k2.5',
    task_alignment_score: 92,
    code_quality_score: 88,
    progress_delta: 12,
    summary: 'Implemented OPPM grid component with timeline rendering',
    quality_flags: ['well-structured'],
    suggestions: [],
    matched_task_id: 't1',
    matched_objective_id: 'o1',
    analyzed_at: new Date().toISOString(),
  },
  {
    id: '2',
    commit_event_id: '2',
    ai_model: 'ollama/codellama',
    task_alignment_score: 67,
    code_quality_score: 74,
    progress_delta: 5,
    summary: 'Fixed sidebar navigation active state and routing',
    quality_flags: ['minor-issues'],
    suggestions: ['Consider extracting nav config to constants'],
    matched_task_id: 't2',
    matched_objective_id: 'o2',
    analyzed_at: new Date(Date.now() - 3600000).toISOString(),
  },
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
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.get<DashboardStats>('/dashboard/stats'),
    placeholderData: DEMO_STATS,
  })

  const s = stats || DEMO_STATS

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

      {/* Charts + Recent Activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Chart */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-text mb-4">Weekly Activity</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={DEMO_CHART}>
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
            {DEMO_RECENT.map((analysis) => (
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
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
