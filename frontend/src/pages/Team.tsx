import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listMembersApiV1WorkspacesWorkspaceIdMembersGet,
  listSkillsRouteApiV1WorkspacesWorkspaceIdMembersMemberIdSkillsGet,
  addSkillRouteApiV1WorkspacesWorkspaceIdMembersMemberIdSkillsPost,
  deleteSkillRouteApiV1WorkspacesWorkspaceIdMembersMemberIdSkillsSkillIdDelete,
} from '@/generated/workspace-api/sdk.gen'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import type { WorkspaceMember, MemberSkill, SkillLevel } from '@/types'
import { cn } from '@/lib/utils'
import { Users, Plus, X, Loader2, Star } from 'lucide-react'
import { WorkspaceMembersPanel } from './settings/WorkspaceMembersPanel'

const LEVEL_STYLES: Record<SkillLevel, string> = {
  beginner: 'bg-slate-100 text-slate-600 border-slate-200',
  intermediate: 'bg-blue-100 text-blue-700 border-blue-200',
  expert: 'bg-emerald-100 text-emerald-700 border-emerald-200',
}

const LEVEL_DOT: Record<SkillLevel, string> = {
  beginner: 'bg-slate-400',
  intermediate: 'bg-blue-500',
  expert: 'bg-emerald-500',
}

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-amber-100 text-amber-700',
  admin: 'bg-purple-100 text-purple-700',
  member: 'bg-blue-100 text-blue-700',
  viewer: 'bg-slate-100 text-slate-600',
}

function MemberCard({
  member,
  wsPath,
  currentMemberId,
  isAdmin,
}: {
  member: WorkspaceMember
  wsPath: string
  currentMemberId: string | null
  isAdmin: boolean
}) {
  const queryClient = useQueryClient()
  const [skillName, setSkillName] = useState('')
  const [skillLevel, setSkillLevel] = useState<SkillLevel>('intermediate')
  const [showAdd, setShowAdd] = useState(false)

  const { data: skills = [], isLoading: loadingSkills } = useQuery<MemberSkill[]>({
    queryKey: ['member-skills', member.id],
    queryFn: () =>
      listSkillsRouteApiV1WorkspacesWorkspaceIdMembersMemberIdSkillsGet({
        client: workspaceClient,
        path: { workspace_id: wsPath.split('/')[3], member_id: member.id },
      }).then((res) => (res.data ?? []) as MemberSkill[]),
  })

  const addSkill = useMutation({
    mutationFn: (data: { skill_name: string; skill_level: SkillLevel }) =>
      addSkillRouteApiV1WorkspacesWorkspaceIdMembersMemberIdSkillsPost({
        client: workspaceClient,
        path: { workspace_id: wsPath.split('/')[3], member_id: member.id },
        body: data,
      }).then((res) => res.data as MemberSkill),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['member-skills', member.id] })
      setSkillName('')
      setSkillLevel('intermediate')
      setShowAdd(false)
    },
  })

  const deleteSkill = useMutation({
    mutationFn: (skillId: string) =>
      deleteSkillRouteApiV1WorkspacesWorkspaceIdMembersMemberIdSkillsSkillIdDelete({
        client: workspaceClient,
        path: { workspace_id: wsPath.split('/')[3], member_id: member.id, skill_id: skillId },
      }).then((res) => res.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['member-skills', member.id] }),
  })

  const canManage = isAdmin || member.id === currentMemberId

  const initial = (member.display_name || member.email || '?').charAt(0).toUpperCase()

  const handleAddSkill = (e: React.FormEvent) => {
    e.preventDefault()
    if (!skillName.trim()) return
    addSkill.mutate({ skill_name: skillName.trim(), skill_level: skillLevel })
  }

  return (
    <div className="rounded-lg border border-border bg-white p-4 flex flex-col gap-4">
      {/* Member header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-surface-alt border border-border text-text font-semibold text-lg">
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-text truncate">
            {member.display_name || member.email?.split('@')[0] || 'Member'}
          </p>
          {member.email && (
            <p className="text-xs text-text-secondary truncate">{member.email}</p>
          )}
        </div>
        <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium capitalize', ROLE_BADGE[member.role] ?? ROLE_BADGE.member)}>
          {member.role}
        </span>
      </div>

      {/* Skills */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center gap-1">
            <Star className="h-3 w-3" /> Skills
          </span>
          {canManage && !showAdd && (
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-1 text-xs text-primary hover:text-primary-dark font-medium"
            >
              <Plus className="h-3.5 w-3.5" /> Add Skill
            </button>
          )}
        </div>

        {loadingSkills ? (
          <div className="flex justify-center py-3">
            <Loader2 className="h-4 w-4 animate-spin text-text-secondary" />
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5 min-h-[2rem]">
            {skills.length === 0 && !showAdd && (
              <p className="text-xs text-text-secondary italic">No skills added yet</p>
            )}
            {skills.map((skill) => (
              <span
                key={skill.id}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
                  LEVEL_STYLES[skill.skill_level]
                )}
              >
                <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', LEVEL_DOT[skill.skill_level])} />
                {skill.skill_name}
                <span className="text-[10px] opacity-70 capitalize">({skill.skill_level})</span>
                {canManage && (
                  <button
                    onClick={() => deleteSkill.mutate(skill.id)}
                    disabled={deleteSkill.isPending}
                    className="ml-0.5 rounded-full hover:opacity-80 transition-opacity"
                    title="Remove skill"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </span>
            ))}
          </div>
        )}

        {/* Add skill form */}
        {showAdd && canManage && (
          <form onSubmit={handleAddSkill} className="mt-3 flex flex-col gap-2">
            <input
              autoFocus
              value={skillName}
              onChange={(e) => setSkillName(e.target.value)}
              placeholder="e.g. React, Python, Design..."
              maxLength={100}
              className="w-full rounded-md border border-border px-3 py-1.5 text-sm outline-none focus:border-text-secondary focus:ring-1 focus:ring-text-secondary/20"
            />
            <div className="flex items-center gap-2">
              <select
                value={skillLevel}
                onChange={(e) => setSkillLevel(e.target.value as SkillLevel)}
                className="flex-1 rounded-md border border-border px-3 py-1.5 text-sm outline-none focus:border-text-secondary"
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="expert">Expert</option>
              </select>
              <button
                type="submit"
                disabled={addSkill.isPending || !skillName.trim()}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50"
              >
                {addSkill.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Add'}
              </button>
              <button
                type="button"
                onClick={() => setShowAdd(false)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-alt"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export function Team() {
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const wsPath = ws ? `/v1/workspaces/${ws.id}` : ''
  const currentUserId = useAuthStore((s) => s.user?.id ?? null)
  const wsRole = ws?.current_user_role ?? ws?.role ?? 'member'
  const isAdmin = wsRole === 'owner' || wsRole === 'admin'

  const { data: members = [], isLoading } = useQuery<WorkspaceMember[]>({
    queryKey: ['workspace-members', ws?.id],
    queryFn: () =>
      listMembersApiV1WorkspacesWorkspaceIdMembersGet({
        client: workspaceClient,
        path: { workspace_id: ws!.id },
      }).then((res) => (res.data ?? []) as WorkspaceMember[]),
    enabled: !!ws,
  })

  // Find the current user's workspace member record
  const currentMember = members.find((m) => m.user_id === currentUserId) ?? null

  if (!ws) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text">Team</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Manage workspace members, invitations, and skills in one place
          </p>
        </div>
        <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-white py-20 text-center">
          <Users className="h-12 w-12 text-text-secondary/30 mb-3" />
          <p className="text-base font-medium text-text">No workspace selected</p>
          <p className="text-sm text-text-secondary mt-1">
            Select or create a workspace to manage your team members and invitations.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text">Team</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          Manage workspace members, invitations, and skills in one place
        </p>
      </div>

      <WorkspaceMembersPanel />

      {/* Legend */}
      <div className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-text">Skill Directory</h2>
          <p className="text-sm text-text-secondary mt-0.5">Use the member cards below for capability tracking and self-managed skills.</p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-text-secondary">
          <span className="font-medium">Skill levels:</span>
          {(['beginner', 'intermediate', 'expert'] as SkillLevel[]).map((level) => (
            <span key={level} className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-medium capitalize', LEVEL_STYLES[level])}>
              <span className={cn('h-1.5 w-1.5 rounded-full', LEVEL_DOT[level])} />
              {level}
            </span>
          ))}
        </div>
      </div>

      {/* Members grid */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : members.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Users className="h-12 w-12 text-text-secondary/30 mb-3" />
          <p className="text-sm text-text-secondary">No members in this workspace yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {members.map((member) => (
            <MemberCard
              key={member.id}
              member={member}
              wsPath={wsPath}
              currentMemberId={currentMember?.id ?? null}
              isAdmin={isAdmin}
            />
          ))}
        </div>
      )}
    </div>
  )
}
