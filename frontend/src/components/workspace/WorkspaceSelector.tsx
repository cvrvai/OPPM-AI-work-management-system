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
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-white/20 px-3 py-2 text-sm text-sidebar-text hover:border-white/40 transition-colors"
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
              className="w-full rounded-lg bg-white/10 px-3 py-1.5 text-sm text-white placeholder:text-white/40 outline-none"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            />
            <div className="flex gap-2">
              <button onClick={handleCreate} className="rounded bg-primary px-3 py-1 text-xs text-white">
                Create
              </button>
              <button onClick={() => setCreating(false)} className="text-xs text-sidebar-text/60">
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
        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white hover:bg-sidebar-hover transition-colors"
      >
        <Building2 className="h-4 w-4 text-primary-light" />
        <span className="flex-1 text-left truncate">{currentWorkspace.name}</span>
        <ChevronDown className={cn('h-4 w-4 text-sidebar-text/60 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute left-3 right-3 top-full z-50 mt-1 rounded-lg border border-white/10 bg-sidebar shadow-xl">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => handleSelect(ws)}
              className={cn(
                'flex w-full items-center gap-2 px-3 py-2 text-sm text-sidebar-text hover:bg-sidebar-hover transition-colors',
                ws.id === currentWorkspace.id && 'bg-sidebar-hover'
              )}
            >
              <Building2 className="h-3.5 w-3.5" />
              <span className="flex-1 text-left truncate">{ws.name}</span>
              {ws.id === currentWorkspace.id && <Check className="h-3.5 w-3.5 text-primary-light" />}
            </button>
          ))}
          <div className="border-t border-white/10">
            {!creating ? (
              <button
                onClick={() => setCreating(true)}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-sidebar-text/60 hover:text-sidebar-text hover:bg-sidebar-hover transition-colors"
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
                  className="w-full rounded bg-white/10 px-2 py-1 text-sm text-white placeholder:text-white/40 outline-none"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
                <div className="flex gap-2">
                  <button onClick={handleCreate} className="rounded bg-primary px-2 py-0.5 text-xs text-white">
                    Create
                  </button>
                  <button onClick={() => { setCreating(false); setNewName('') }} className="text-xs text-sidebar-text/60">
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
