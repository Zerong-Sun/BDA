import { z } from 'zod'
import { JobStatusSchema } from './workflow'

export const JobSchema = z.object({
  id: z.string(), submission_id: z.string(), workflow_run_id: z.string(), workflow_node_id: z.string(),
  project_id: z.string(), status: JobStatusSchema, compute_backend: z.string(), model_plugin: z.string(),
  attempt_number: z.number(), external_id: z.string().nullable(), next_poll_at: z.string().nullable(),
  timeout_at: z.string().nullable(), error_code: z.string().nullable(), error_message: z.string().nullable(),
  version: z.number(), created_at: z.string(), updated_at: z.string(),
})

export type Job = z.infer<typeof JobSchema>
