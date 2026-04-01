import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { CommitEvent, CommitAnalysis } from '@/types'
import { cn, formatRelativeTime, getProgressColor } from '@/lib/utils'
import {
  GitCommitHorizontal,
  Target,
  Shield,
  TrendingUp,
  FileCode,
  User,
  GitBranch,
} from 'lucide-react'

const DEMO_COMMITS: (CommitEvent & { analysis?: CommitAnalysis })[] = [
  {
    id: '1', repo_config_id: 'r1',
    commit_hash: 'a3f8c2d', commit_message: 'feat: implement OPPM Gantt hybrid view with week navigation',
    author_github_username: 'cvrvai', branch: 'main',
    files_changed: ['src/pages/OPPMView.tsx', 'src/types/index.ts'],
    additions: 285, deletions: 12, pushed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    analysis: {
      id: 'a1', commit_event_id: '1', ai_model: 'kimi-k2.5',
      task_alignment_score: 95, code_quality_score: 88, progress_delta: 15,
      summary: 'Implements the core OPPM Gantt matrix view with week-by-week dot status indicators. Well-structured component with clear separation of demo data and rendering logic.',
      quality_flags: ['well-structured', 'good-types'],
      suggestions: ['Consider memoizing week generation', 'Add error boundary'],
      matched_task_id: 't2', matched_objective_id: 'o2',
      analyzed_at: new Date().toISOString(),
    },
  },
  {
    id: '2', repo_config_id: 'r1',
    commit_hash: 'b7e1a9f', commit_message: 'feat: add sidebar navigation and layout system',
    author_github_username: 'cvrvai', branch: 'main',
    files_changed: ['src/components/layout/Sidebar.tsx', 'src/components/layout/Layout.tsx', 'src/components/layout/Header.tsx'],
    additions: 142, deletions: 0, pushed_at: new Date(Date.now() - 7200000).toISOString(),
    created_at: new Date(Date.now() - 7200000).toISOString(),
    analysis: {
      id: 'a2', commit_event_id: '2', ai_model: 'ollama/codellama',
      task_alignment_score: 78, code_quality_score: 82, progress_delta: 10,
      summary: 'Sets up the main application layout with dark sidebar, sticky header, and outlet-based routing. Clean and standard approach.',
      quality_flags: ['clean-code'],
      suggestions: ['Add responsive mobile sidebar toggle'],
      matched_task_id: 't1', matched_objective_id: 'o1',
      analyzed_at: new Date(Date.now() - 7200000).toISOString(),
    },
  },
  {
    id: '3', repo_config_id: 'r1',
    commit_hash: 'c4d2e8b', commit_message: 'fix: correct auth redirect flow and session handling',
    author_github_username: 'cvrvai', branch: 'main',
    files_changed: ['src/App.tsx', 'src/stores/authStore.ts'],
    additions: 35, deletions: 18, pushed_at: new Date(Date.now() - 14400000).toISOString(),
    created_at: new Date(Date.now() - 14400000).toISOString(),
    analysis: {
      id: 'a3', commit_event_id: '3', ai_model: 'kimi-k2.5',
      task_alignment_score: 60, code_quality_score: 90, progress_delta: 3,
      summary: 'Fixes authentication redirect loop. Session initialization now properly awaits before rendering protected routes.',
      quality_flags: ['bug-fix', 'security-aware'],
      suggestions: [],
      matched_task_id: 't1b', matched_objective_id: 'o1',
      analyzed_at: new Date(Date.now() - 14400000).toISOString(),
    },
  },
]

function ScoreBadge({
  value,
  label,
  icon: Icon,
}: {
  value: number
  label: string
  icon: React.ElementType
}) {
  const bg =
    value >= 80 ? 'bg-emerald-50 text-emerald-700' :
    value >= 60 ? 'bg-blue-50 text-blue-700' :
    value >= 40 ? 'bg-amber-50 text-amber-700' :
    'bg-red-50 text-red-700'

  return (
    <div className={cn('flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', bg)}>
      <Icon className="h-3 w-3" />
      <span>{label}</span>
      <span className="font-bold">{value}%</span>
    </div>
  )
}

export function Commits() {
  const { data: commits } = useQuery({
    queryKey: ['commits'],
    queryFn: () => api.get<(CommitEvent & { analysis?: CommitAnalysis })[]>('/commits'),
    placeholderData: DEMO_COMMITS,
  })

  const list = commits || DEMO_COMMITS

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text">Commit Activity</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          AI-analyzed commits from your GitHub repositories
        </p>
      </div>

      {/* Commit List */}
      <div className="space-y-4">
        {list.map((commit) => (
          <div
            key={commit.id}
            className="rounded-xl border border-border bg-white p-5 shadow-sm"
          >
            {/* Commit Header */}
            <div className="flex items-start gap-3 mb-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50 mt-0.5">
                <GitCommitHorizontal className="h-4.5 w-4.5 text-violet-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-text">{commit.commit_message}</h3>
                <div className="flex items-center gap-3 mt-1 text-xs text-text-secondary">
                  <span className="flex items-center gap-1">
                    <User className="h-3 w-3" />
                    {commit.author_github_username}
                  </span>
                  <span className="flex items-center gap-1">
                    <GitBranch className="h-3 w-3" />
                    {commit.branch}
                  </span>
                  <span className="font-mono text-[10px] bg-surface-alt px-1.5 py-0.5 rounded">
                    {commit.commit_hash}
                  </span>
                  <span>{formatRelativeTime(commit.pushed_at)}</span>
                </div>
              </div>
              <div className="text-right text-xs text-text-secondary">
                <span className="text-emerald-600">+{commit.additions}</span>{' '}
                <span className="text-red-500">-{commit.deletions}</span>
              </div>
            </div>

            {/* Files Changed */}
            <div className="mb-3">
              <div className="flex flex-wrap gap-1.5">
                {commit.files_changed.map((file) => (
                  <span
                    key={file}
                    className="flex items-center gap-1 rounded bg-surface-alt px-2 py-0.5 text-[10px] text-text-secondary font-mono"
                  >
                    <FileCode className="h-2.5 w-2.5" />
                    {file}
                  </span>
                ))}
              </div>
            </div>

            {/* AI Analysis */}
            {commit.analysis && (
              <div className="rounded-lg border border-border bg-surface-alt/50 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-medium text-text-secondary uppercase tracking-wider">
                    AI Analysis — {commit.analysis.ai_model}
                  </span>
                </div>

                {/* Scores */}
                <div className="flex flex-wrap gap-2">
                  <ScoreBadge
                    value={commit.analysis.task_alignment_score}
                    label="Alignment"
                    icon={Target}
                  />
                  <ScoreBadge
                    value={commit.analysis.code_quality_score}
                    label="Quality"
                    icon={Shield}
                  />
                  <ScoreBadge
                    value={commit.analysis.progress_delta}
                    label="Progress"
                    icon={TrendingUp}
                  />
                </div>

                {/* Summary */}
                <p className="text-xs text-text-secondary leading-relaxed">
                  {commit.analysis.summary}
                </p>

                {/* Quality Flags + Suggestions */}
                <div className="flex flex-wrap gap-1.5">
                  {commit.analysis.quality_flags.map((flag) => (
                    <span
                      key={flag}
                      className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700"
                    >
                      {flag}
                    </span>
                  ))}
                </div>

                {commit.analysis.suggestions.length > 0 && (
                  <div className="text-xs text-text-secondary">
                    <span className="font-medium">Suggestions: </span>
                    {commit.analysis.suggestions.join(' • ')}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
