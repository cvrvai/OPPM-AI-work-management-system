import { z } from 'zod'

export const WorkspaceRoleSchema = z.enum(['owner', 'admin', 'member', 'viewer'])

export const WorkspaceSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  slug: z.string().min(1),
  description: z.string().nullable(),
  created_by: z.string().uuid(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  role: WorkspaceRoleSchema.optional(),
  current_user_role: WorkspaceRoleSchema.optional(),
})

export const WorkspaceMemberSchema = z.object({
  id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  user_id: z.string().uuid(),
  role: WorkspaceRoleSchema,
  joined_at: z.string().datetime(),
  email: z.string().email().optional(),
  display_name: z.string().optional(),
})

export const WorkspaceInviteSchema = z.object({
  id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  email: z.string().email(),
  role: WorkspaceRoleSchema,
  invited_by: z.string().uuid(),
  token: z.string(),
  expires_at: z.string().datetime(),
  accepted_at: z.string().datetime().nullable(),
  created_at: z.string().datetime().optional(),
  sent_at: z.string().datetime().nullable().optional(),
  is_new_user: z.boolean().optional(),
})

export const PaginatedResponseSchema = <T extends z.ZodType>(schema: T) =>
  z.object({
    items: z.array(schema),
    total: z.number().int().nonnegative(),
    page: z.number().int().optional(),
    page_size: z.number().int().optional(),
  })
