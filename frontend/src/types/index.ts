// ── Workspace ──
export type WorkspaceRole = 'owner' | 'admin' | 'member' | 'viewer'

export interface Workspace {
  id: string
  name: string
  slug: string
  description: string | null
  created_by: string
  created_at: string
  updated_at: string
  role?: WorkspaceRole
  current_user_role?: WorkspaceRole
}

export interface WorkspaceMember {
  id: string
  workspace_id: string
  user_id: string
  role: WorkspaceRole
  joined_at: string
  email?: string
  display_name?: string
}

export type SkillLevel = 'beginner' | 'intermediate' | 'expert'

export interface MemberSkill {
  id: string
  workspace_member_id: string
  skill_name: string
  skill_level: SkillLevel
  created_at: string
}

export interface WorkspaceInvite {
  id: string
  workspace_id: string
  email: string
  role: WorkspaceRole
  invited_by: string
  token: string
  expires_at: string
  accepted_at: string | null
  created_at?: string
  sent_at?: string | null
  is_new_user?: boolean
}

export interface MyInvite {
  id: string
  workspace_id: string
  workspace_name: string
  workspace_slug: string
  inviter_name: string
  role: WorkspaceRole
  token: string
  expires_at: string
  created_at: string
  is_expired: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

// ── Project ──
export type ProjectStatus = 'planning' | 'in_progress' | 'completed' | 'on_hold' | 'cancelled'
export type Priority = 'low' | 'medium' | 'high' | 'critical'

export interface Project {
  id: string
  workspace_id: string
  title: string
  description: string
  project_code: string | null
  objective_summary: string | null
  deliverable_output: string | null
  status: ProjectStatus
  priority: Priority
  progress: number
  budget: number
  planning_hours: number
  start_date: string | null
  deadline: string | null
  end_date: string | null
  metadata?: Record<string, unknown>
  lead_id: string | null
  lead?: WorkspaceMember
  created_at: string
  updated_at: string
}

export interface ProjectMember {
  id: string
  project_id: string
  workspace_member_id: string
  role: string
  joined_at: string
  display_name?: string
  email?: string
}

// ── Task ──
export type TaskStatus = 'todo' | 'in_progress' | 'completed'

export interface TaskOwner {
  member_id: string
  display_name?: string | null
  priority: 'A' | 'B' | 'C'
}

export interface Task {
  id: string
  title: string
  description: string
  project_id: string
  status: TaskStatus
  priority: Priority
  progress: number
  project_contribution: number
  sort_order: number
  start_date: string | null
  due_date: string | null
  assignee_id: string | null
  parent_task_id?: string | null
  created_by: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  oppm_objective_id?: string | null
  depends_on: string[]
  assignees?: { id: string; display_name?: string | null }[]
  owners?: TaskOwner[]
  sub_objective_ids?: string[]
}

export interface TaskReport {
  id: string
  task_id: string
  reporter_id: string
  report_date: string
  hours: number
  description: string
  is_approved: boolean
  approved_by: string | null
  approved_at: string | null
  created_at: string
}

// ── OPPM ──
export interface OPPMObjective {
  id: string
  project_id: string
  title: string
  owner_id: string | null
  priority?: string | null
  owner?: WorkspaceMember
  sort_order: number
  tasks: Task[]
}

export interface OPPMSubObjective {
  id: string
  project_id: string
  position: number
  label: string
  created_at: string
}

export interface OPPMTimelineEntry {
  id: string
  project_id: string
  task_id: string
  week_start: string
  status: 'planned' | 'in_progress' | 'completed' | 'at_risk' | 'blocked'
  quality?: 'good' | 'average' | 'bad' | null
  ai_score?: number | null
  notes?: string | null
  created_at: string
}

export interface OPPMCost {
  id: string
  project_id: string
  category: string
  planned_amount: number
  actual_amount: number
  description: string
  created_at: string
}

export interface OPPMDeliverable {
  id: string
  project_id: string
  item_number: number
  description: string
  created_at: string
}

export interface OPPMForecast {
  id: string
  project_id: string
  item_number: number
  description: string
  created_at: string
}

export type RagStatus = 'green' | 'amber' | 'red'

export interface OPPMRisk {
  id: string
  project_id: string
  item_number: number
  description: string
  rag: RagStatus
  created_at: string
}

// ── Member (legacy compatibility) ──
export interface Member {
  id: string
  name: string
  email: string
  avatar_url: string | null
  role: string
}

// ── Git / Commits ──
export interface GitAccount {
  id: string
  account_name: string
  github_username: string
  created_at: string
}

export interface RepoConfig {
  id: string
  repo_name: string
  project_id: string
  github_account_id: string
  webhook_secret: string
  is_active: boolean
}

export interface CommitEvent {
  id: string
  repo_config_id: string
  commit_hash: string
  commit_message: string
  author_github_username: string
  branch: string
  files_changed: string[]
  additions: number
  deletions: number
  pushed_at: string
  created_at: string
}

export interface CommitAnalysis {
  id: string
  commit_event_id: string
  ai_model: string
  task_alignment_score: number
  code_quality_score: number
  progress_delta: number
  summary: string
  quality_flags: string[]
  suggestions: string[]
  matched_task_id: string | null
  matched_objective_id: string | null
  analyzed_at: string
}

// ── AI Models ──
export interface AIModel {
  id: string
  name: string
  provider: 'ollama' | 'anthropic' | 'openai' | 'kimi' | 'custom'
  model_id: string
  is_active: boolean
  endpoint_url: string | null
}

// ── Dashboard Stats ──
export interface ProjectProgress {
  project_id: string
  title: string
  progress: number
  status: string
}

export interface DashboardStats {
  total_projects: number
  active_projects: number
  total_tasks: number
  completed_tasks: number
  total_commits_today: number
  avg_quality_score: number
  avg_alignment_score: number
  project_progress: ProjectProgress[]
}

// ── Notifications ──
export type NotificationType = 'info' | 'success' | 'warning' | 'error' | 'ai_analysis' | 'commit' | 'task_update'

export interface Notification {
  id: string
  user_id: string | null
  type: NotificationType
  title: string
  message: string
  is_read: boolean
  link: string | null
  metadata: Record<string, unknown>
  created_at: string
}
