import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, X, Users, UserPlus } from 'lucide-react'
import { api } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'

interface VirtualMember {
  id: string
  name: string
  email?: string | null
  role?: string | null
  created_at?: string
}

interface WorkspaceMember {
  id: string
  user_id: string
  display_name?: string | null
  email?: string | null
  role?: string | null
}

interface ProjectAllMember {
  id: string
  member_id: string
  source: 'workspace' | 'virtual'
  name: string
  display_order: number
  is_leader: boolean
}

interface VirtualMemberManagerProps {
  projectId: string
  onClose?: () => void
}

export function VirtualMemberManager({ projectId, onClose }: VirtualMemberManagerProps) {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const queryClient = useQueryClient()
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''

  const [isOpen, setIsOpen] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('')
  const [error, setError] = useState<string | null>(null)

  const isControlled = !!onClose
  const showModal = isControlled || isOpen

  const handleClose = () => {
    if (isControlled) {
      onClose()
    } else {
      setIsOpen(false)
    }
  }

  const virtualMembersQuery = useQuery({
    queryKey: ['virtual-members', projectId, ws?.id],
    queryFn: () => api.get<{ items: VirtualMember[] }>(`${wsPath}/projects/${projectId}/oppm/virtual-members`),
    enabled: !!ws && !!projectId && showModal,
  })

  const workspaceMembersQuery = useQuery({
    queryKey: ['workspace-members', ws?.id],
    queryFn: () => api.get<WorkspaceMember[]>(`${wsPath}/members`),
    enabled: !!ws && showModal,
    staleTime: 5 * 60 * 1000,
  })

  const allMembersQuery = useQuery({
    queryKey: ['all-members', projectId, ws?.id],
    queryFn: () => api.get<{ items: ProjectAllMember[] }>(`${wsPath}/projects/${projectId}/oppm/all-members`),
    enabled: !!ws && !!projectId && showModal,
  })

  const createVirtualMember = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error('Name is required')
      return api.post<VirtualMember>(`${wsPath}/projects/${projectId}/oppm/virtual-members`, {
        name: name.trim(),
        email: email.trim() || undefined,
        role,
      })
    },
    onSuccess: () => {
      setName('')
      setEmail('')
      setRole('')
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['virtual-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['all-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold', projectId, ws?.id] })
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteVirtualMember = useMutation({
    mutationFn: (memberId: string) =>
      api.delete(`${wsPath}/oppm/virtual-members/${memberId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['virtual-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['all-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold', projectId, ws?.id] })
    },
  })

  const addVirtualMemberToProject = useMutation({
    mutationFn: (virtualMemberId: string) =>
      api.post(`${wsPath}/projects/${projectId}/oppm/all-members/virtual/${virtualMemberId}`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold', projectId, ws?.id] })
    },
  })

  const addWorkspaceMemberToProject = useMutation({
    mutationFn: (workspaceMemberId: string) =>
      api.post(`${wsPath}/projects/${projectId}/oppm/all-members/workspace/${workspaceMemberId}`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold', projectId, ws?.id] })
    },
  })

  const removeFromAllMembers = useMutation({
    mutationFn: (allMemberId: string) =>
      api.delete(`${wsPath}/oppm/all-members/${allMemberId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-members', projectId, ws?.id] })
      queryClient.invalidateQueries({ queryKey: ['oppm-scaffold', projectId, ws?.id] })
    },
  })

  const virtualMembers = virtualMembersQuery.data?.items ?? []
  const workspaceMembers = workspaceMembersQuery.data ?? []
  const allMembers = allMembersQuery.data?.items ?? []

  const workspaceInProject = new Set(
    allMembers.filter((m) => m.source === 'workspace').map((m) => m.member_id)
  )
  const virtualInProject = new Set(
    allMembers.filter((m) => m.source === 'virtual').map((m) => m.member_id)
  )

  const activeWorkspaceMembers = allMembers.filter((m) => m.source === 'workspace')
  const activeExternalMembers = allMembers.filter((m) => m.source === 'virtual')

  return (
    <>
      {!isControlled && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          title="Manage project members including external stakeholders"
        >
          <Users className="h-3 w-3" />
          Members
        </button>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-gray-900">Project Members</h2>
              <button
                type="button"
                onClick={handleClose}
                className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[70vh] overflow-y-auto px-4 py-4">
              {/* Add Virtual Member Form */}
              <div className="mb-4 rounded-lg border border-gray-100 bg-gray-50 p-3">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Add External Member</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Name *"
                      className="flex-1 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-900 outline-none focus:border-blue-500"
                    />
                    <input
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Email (optional)"
                      className="flex-1 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-900 outline-none focus:border-blue-500"
                    />
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      placeholder="Role (e.g. Full Stack, ML, DevOps)"
                      className="flex-1 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-900 outline-none focus:border-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => createVirtualMember.mutate()}
                      disabled={createVirtualMember.isPending || !name.trim()}
                      className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      <UserPlus className="h-3 w-3" />
                      Add
                    </button>
                  </div>
                  {error && <p className="text-xs text-red-600">{error}</p>}
                </div>
              </div>

              {/* ── Workspace Members (Internal) ── */}
              {workspaceMembers.length > 0 && (
                <div className="mb-4">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Workspace Members ({workspaceMembers.length})
                  </h3>
                  <div className="flex flex-col gap-1.5">
                    {workspaceMembers.map((wm) => {
                      const isInProject = workspaceInProject.has(wm.id)
                      const allMemberEntry = allMembers.find(
                        (m) => m.member_id === wm.id && m.source === 'workspace'
                      )
                      return (
                        <div
                          key={wm.id}
                          className="flex items-center justify-between rounded-md border border-gray-100 bg-white px-3 py-2"
                        >
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700">
                              S
                            </span>
                            <div className="min-w-0">
                              <p className="text-xs font-medium text-gray-900 truncate">
                                {wm.display_name || wm.email || wm.id.slice(0, 8)}
                              </p>
                              {wm.email && (
                                <p className="text-[10px] text-gray-500 truncate">{wm.email}</p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {isInProject ? (
                              <button
                                type="button"
                                onClick={() =>
                                  allMemberEntry && removeFromAllMembers.mutate(allMemberEntry.id)
                                }
                                disabled={removeFromAllMembers.isPending}
                                className="rounded-md border border-red-200 px-2 py-1 text-[10px] font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                              >
                                Remove
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => addWorkspaceMemberToProject.mutate(wm.id)}
                                disabled={addWorkspaceMemberToProject.isPending}
                                className="rounded-md border border-gray-200 px-2 py-1 text-[10px] font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                              >
                                Add to Project
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* External Members Pool */}
              {virtualMembers.length > 0 && (
                <div className="mb-4">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">External Members Pool</h3>
                  <div className="flex flex-col gap-1.5">
                    {virtualMembers.map((vm) => {
                      const isInProject = virtualInProject.has(vm.id)
                      const allMemberEntry = allMembers.find((m) => m.member_id === vm.id && m.source === 'virtual')
                      return (
                        <div
                          key={vm.id}
                          className="flex items-center justify-between rounded-md border border-gray-100 bg-white px-3 py-2"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium text-gray-900">{vm.name}</p>
                            {vm.email && <p className="text-[10px] text-gray-500">{vm.email}</p>}
                            {vm.role && <p className="text-[10px] text-gray-400 capitalize">{vm.role}</p>}
                          </div>
                          <div className="flex items-center gap-1.5">
                            {isInProject ? (
                              <button
                                type="button"
                                onClick={() => allMemberEntry && removeFromAllMembers.mutate(allMemberEntry.id)}
                                disabled={removeFromAllMembers.isPending}
                                className="rounded-md border border-red-200 px-2 py-1 text-[10px] font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                              >
                                Remove
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => addVirtualMemberToProject.mutate(vm.id)}
                                disabled={addVirtualMemberToProject.isPending}
                                className="rounded-md border border-gray-200 px-2 py-1 text-[10px] font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                              >
                                Add to Project
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => deleteVirtualMember.mutate(vm.id)}
                              disabled={deleteVirtualMember.isPending}
                              className="rounded-md p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                              title="Delete external member"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* ── Active Project Members ── */}
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Active Project Members ({allMembers.length})
                </h3>
                {allMembers.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">No members assigned to this project yet.</p>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {/* System members first */}
                    {activeWorkspaceMembers.length > 0 && (
                      <div className="mb-1">
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-blue-600">
                          System ({activeWorkspaceMembers.length})
                        </p>
                        <div className="flex flex-col gap-1.5">
                          {activeWorkspaceMembers.map((m) => (
                            <div
                              key={m.id}
                              className="flex items-center justify-between rounded-md border border-gray-100 bg-white px-3 py-2"
                            >
                              <div className="flex items-center gap-2">
                                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700">
                                  S
                                </span>
                                <div>
                                  <p className="text-xs font-medium text-gray-900">{m.name}</p>
                                  <p className="text-[10px] text-gray-400">System member</p>
                                </div>
                              </div>
                              {m.is_leader && (
                                <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-[10px] font-medium text-yellow-700">
                                  Leader
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* External members */}
                    {activeExternalMembers.length > 0 && (
                      <div>
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-amber-600">
                          External ({activeExternalMembers.length})
                        </p>
                        <div className="flex flex-col gap-1.5">
                          {activeExternalMembers.map((m) => (
                            <div
                              key={m.id}
                              className="flex items-center justify-between rounded-md border border-gray-100 bg-white px-3 py-2"
                            >
                              <div className="flex items-center gap-2">
                                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-700">
                                  E
                                </span>
                                <div>
                                  <p className="text-xs font-medium text-gray-900">{m.name}</p>
                                  <p className="text-[10px] text-gray-400">External member</p>
                                </div>
                              </div>
                              {m.is_leader && (
                                <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-[10px] font-medium text-yellow-700">
                                  Leader
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="border-t border-gray-100 px-4 py-3">
              <button
                type="button"
                onClick={handleClose}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
