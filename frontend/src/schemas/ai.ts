import { z } from 'zod'

export const ChatMessageSchema = z.object({
  role: z.enum(['user', 'assistant', 'system']),
  content: z.string(),
  timestamp: z.string().datetime().optional(),
})

export const ToolCallResultSchema = z.object({
  tool: z.string(),
  input: z.record(z.string(), z.unknown()),
  result: z.record(z.string(), z.unknown()),
  success: z.boolean(),
  error: z.string().nullable().optional(),
})

export const ChatResponseSchema = z.object({
  message: z.string(),
  tool_calls: z.array(ToolCallResultSchema),
  updated_entities: z.array(z.string()),
})

export const CommitAnalysisSchema = z.object({
  id: z.string().uuid(),
  commit_id: z.string(),
  summary: z.string(),
  impact: z.enum(['low', 'medium', 'high', 'critical']).optional(),
  created_at: z.string().datetime(),
})
