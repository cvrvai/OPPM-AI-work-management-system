import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatContext } from '@/hooks/useChatContext'
import type { CommitEvent, CommitAnalysis } from '@/types'
import { cn, formatRelativeTime } from '@/lib/utils'
import {
  GitCommitHorizontal,
  Target,
  Shield,
  TrendingUp,
  FileCode,
  User,
  GitBranch,
  Loader2,
} from 'lucide-react'

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
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  useChatContext('workspace')

  const { data: commits, isLoading } = useQuery({
    queryKey: ['commits', ws?.id],
    queryFn: () => api.get<(CommitEvent & { analysis?: CommitAnalysis })[]>(`${wsPath}/commits`),
    enabled: !!ws,
  })

  const list = commits || []

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
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : list.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <GitCommitHorizontal className="h-12 w-12 text-text-secondary/30 mb-3" />
          <p className="text-sm text-text-secondary">
            No commits yet. Push commits to a linked repository to see them here.
          </p>
        </div>
      ) : (
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
      )}
    </div>
  )
}
