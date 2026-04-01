// ── Project ──
export type ProjectStatus = 'planning' | 'in_progress' | 'completed' | 'on_hold' | 'cancelled'
export type Priority = 'low' | 'medium' | 'high' | 'critical'

export interface Project {
  id: string
  title: string
  description: string
  status: ProjectStatus
  priority: Priority
  progress: number
  start_date: string | null
  deadline: string | null
  lead_id: string | null
  lead?: Member
  created_at: string
  updated_at: string
}

// ── Task ──
export type TaskStatus = 'todo' | 'in_progress' | 'completed'

export interface Task {
  id: string
  title: string
  description: string
  project_id: string
  status: TaskStatus
  priority: Priority
  progress: number
  project_contribution: number
  due_date: string | null
  created_by: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  assignees?: Member[]
  oppm_objective_id?: string | null
}

// ── OPPM ──
export interface OPPMObjective {
  id: string
  project_id: string
  title: string
  owner_id: string | null
  owner?: Member
  sort_order: number
  tasks: Task[]
}

export interface OPPMTimelineEntry {
  id: string
  project_id: string
  objective_id: string
  week_start: string
  status: 'planned' | 'in_progress' | 'completed' | 'at_risk' | 'blocked'
  ai_score: number | null
  notes: string | null
}

// ── Member ──
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
export interface DashboardStats {
  total_projects: number
  active_projects: number
  total_tasks: number
  completed_tasks: number
  total_commits_today: number
  avg_quality_score: number
  avg_alignment_score: number
}
