import { useEffect, useState } from 'react'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import { Building2, Plus, ChevronDown, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Workspace } from '@/types'

export function WorkspaceSelector() {
  const { workspaces, currentWorkspace, setCurrentWorkspace, fetchWorkspaces, createWorkspace } =
    useWorkspaceStore()
  const user = useAuthStore((s) => s.user)
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')

  useEffect(() => {
    if (user) fetchWorkspaces()
  }, [user, fetchWorkspaces])

  const handleCreate = async () => {
    if (!newName.trim()) return
    const slug = newName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
    await createWorkspace(newName.trim(), slug)
    setCreating(false)
    setNewName('')
    setOpen(false)
  }

  const handleSelect = (ws: Workspace) => {
    setCurrentWorkspace(ws)
    setOpen(false)
  }

  if (!currentWorkspace) {
    return (
      <div className="px-3 py-2">
        <button
          onClick={() => setCreating(true)}
          className="flex w-full items-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm text-text-secondary hover:border-text-secondary transition-colors"
        >
          <Plus className="h-4 w-4" />
          Create Workspace
        </button>
        {creating && (
          <div className="mt-2 space-y-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Workspace name"
              className="w-full rounded-md bg-white border border-border px-3 py-1.5 text-sm text-text placeholder:text-text-secondary outline-none"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            />
            <div className="flex gap-2">
              <button onClick={handleCreate} className="rounded-md bg-primary px-3 py-1 text-xs text-white">
                Create
              </button>
              <button onClick={() => setCreating(false)} className="text-xs text-text-secondary">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="relative px-3 py-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-text hover:bg-sidebar-hover transition-colors"
      >
        <Building2 className="h-4 w-4 text-text-secondary" />
        <span className="flex-1 text-left truncate">{currentWorkspace.name}</span>
        <ChevronDown className={cn('h-4 w-4 text-text-secondary transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute left-3 right-3 top-full z-50 mt-1 rounded-md border border-border bg-white shadow-md">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => handleSelect(ws)}
              className={cn(
                'flex w-full items-center gap-2 px-3 py-2 text-sm text-text hover:bg-surface-alt transition-colors',
                ws.id === currentWorkspace.id && 'bg-surface-alt'
              )}
            >
              <Building2 className="h-3.5 w-3.5 text-text-secondary" />
              <span className="flex-1 text-left truncate">{ws.name}</span>
              {ws.id === currentWorkspace.id && <Check className="h-3.5 w-3.5 text-text-secondary" />}
            </button>
          ))}
          <div className="border-t border-border">
            {!creating ? (
              <button
                onClick={() => setCreating(true)}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:text-text hover:bg-surface-alt transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                New Workspace
              </button>
            ) : (
              <div className="p-2 space-y-2">
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Workspace name"
                  className="w-full rounded-md bg-white border border-border px-2 py-1 text-sm text-text placeholder:text-text-secondary outline-none"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
                <div className="flex gap-2">
                  <button onClick={handleCreate} className="rounded-md bg-primary px-2 py-0.5 text-xs text-white">
                    Create
                  </button>
                  <button onClick={() => { setCreating(false); setNewName('') }} className="text-xs text-text-secondary">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
