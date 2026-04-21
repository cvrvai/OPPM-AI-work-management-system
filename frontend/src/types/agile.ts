// ── Agile Types ──

export type EpicStatus = 'open' | 'in_progress' | 'done'
export type UserStoryStatus = 'draft' | 'ready' | 'in_progress' | 'done' | 'rejected'
export type SprintStatus = 'planning' | 'active' | 'completed' | 'cancelled'

export interface Epic {
  id: string
  workspace_id: string
  project_id: string
  title: string
  description: string
  status: EpicStatus
  priority: string
  position: number
  created_at: string
  updated_at: string
}

export interface AcceptanceCriterion {
  criterion: string
  met: boolean
}

export interface UserStory {
  id: string
  workspace_id: string
  project_id: string
  epic_id: string | null
  sprint_id: string | null
  task_id: string | null
  title: string
  description: string
  acceptance_criteria: AcceptanceCriterion[]
  story_points: number | null
  priority: string
  status: UserStoryStatus
  position: number
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface Sprint {
  id: string
  workspace_id: string
  project_id: string
  name: string
  goal: string | null
  sprint_number: number
  start_date: string | null
  end_date: string | null
  status: SprintStatus
  velocity: number | null
  created_at: string
  updated_at: string
}

export interface ActionItem {
  item: string
  assignee_id: string | null
  done: boolean
}

export interface Retrospective {
  id: string
  workspace_id: string
  project_id: string
  sprint_id: string
  went_well: string[]
  to_improve: string[]
  action_items: ActionItem[]
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface BurndownData {
  total_points: number
  done_points: number
  dates: string[]
  ideal: number[]
  actual: number[]
}
