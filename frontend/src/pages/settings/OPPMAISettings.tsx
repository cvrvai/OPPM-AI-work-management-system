import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOppmSheetPrompt, updateOppmSheetPrompt, resetOppmSheetPrompt } from '@/lib/api'
import { Loader2 } from 'lucide-react'

export function OPPMAISettings({ workspaceId }: { workspaceId: string }) {
  const [draft, setDraft] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['oppm-sheet-prompt', workspaceId],
    queryFn: () => getOppmSheetPrompt(workspaceId),
  })

  const queryClient = useQueryClient()

  const saveMutation = useMutation({
    mutationFn: (prompt: string) => updateOppmSheetPrompt(workspaceId, prompt),
    onSuccess: (data) => {
      queryClient.setQueryData(['oppm-sheet-prompt', workspaceId], data)
      setDraft(null)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => resetOppmSheetPrompt(workspaceId),
    onSuccess: (data) => {
      queryClient.setQueryData(['oppm-sheet-prompt', workspaceId], data)
      setDraft(null)
    },
  })

  const currentPrompt = data?.prompt ?? ''
  const isDefault = data?.is_default ?? true
  const displayValue = draft !== null ? draft : currentPrompt

  if (isLoading) {
    return <div className="flex items-center gap-2 text-sm text-text-secondary"><Loader2 className="h-4 w-4 animate-spin" /> Loading...</div>
  }
  if (error) {
    return <p className="text-sm text-red-600">Failed to load OPPM AI settings.</p>
  }

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="text-base font-semibold text-text">OPPM Sheet System Prompt</h3>
        {isDefault && (
          <span className="text-xs bg-blue-50 text-blue-600 border border-blue-200 rounded-full px-2 py-0.5">
            Using default
          </span>
        )}
      </div>
      <p className="text-sm text-text-secondary">
        This prompt instructs the AI how to control the linked Google Sheet. It defines the 12 available actions, decision rules, and output format.
      </p>
      <textarea
        value={displayValue}
        onChange={(e) => setDraft(e.target.value)}
        rows={20}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm font-mono text-text focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary resize-y"
      />
      <div className="flex items-center gap-3">
        <button
          onClick={() => { if (draft !== null) saveMutation.mutate(draft) }}
          disabled={draft === null || draft.trim().length < 50 || saveMutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
        >
          {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {saved ? 'Saved!' : 'Save Prompt'}
        </button>
        {!isDefault && (
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className="text-sm text-text-secondary hover:text-red-600 underline"
          >
            {resetMutation.isPending ? 'Resetting...' : 'Reset to default'}
          </button>
        )}
        {draft !== null && (
          <button
            onClick={() => setDraft(null)}
            className="text-sm text-text-secondary hover:text-text"
          >
            Discard changes
          </button>
        )}
      </div>
      {saveMutation.isError && (
        <p className="text-sm text-red-600">{saveMutation.error instanceof Error ? saveMutation.error.message : 'Save failed'}</p>
      )}
    </div>
  )
}
