import { z } from 'zod'
import { WorkspaceMemberSchema } from './workspace'

export const ProjectStatusSchema = z.enum(['planning', 'in_progress', 'completed', 'on_hold', 'cancelled'])
export const PrioritySchema = z.enum(['low', 'medium', 'high', 'critical'])
export const MethodologySchema = z.enum(['agile', 'waterfall', 'hybrid', 'oppm'])

export const ProjectSchema = z.object({
  id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  title: z.string().min(1),
  description: z.string(),
  project_code: z.string().nullable(),
  objective_summary: z.string().nullable(),
  deliverable_output: z.string().nullable(),
  status: ProjectStatusSchema,
  priority: PrioritySchema,
  progress: z.number().min(0).max(100),
  budget: z.number(),
  planning_hours: z.number(),
  start_date: z.string().datetime().nullable(),
  deadline: z.string().datetime().nullable(),
  end_date: z.string().datetime().nullable(),
  metadata: z.record(z.string(), z.unknown()).optional(),
  methodology: MethodologySchema,
  lead_id: z.string().uuid().nullable(),
  lead: WorkspaceMemberSchema.optional(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
})

export const ProjectMemberSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  user_id: z.string().uuid(),
  role: z.string(),
  joined_at: z.string().datetime(),
})
