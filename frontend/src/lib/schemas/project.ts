import { z } from 'zod'
import { TargetReadinessSchema } from './target'

export const ProjectSchema = z.object({
  id: z.string(),
  legacy_id: z.string().nullable().optional(),
  organization_id: z.string(),
  owner_id: z.string(),
  name: z.string(),
  project_type: z.string(),
  summary: z.string().nullable(),
  prompt: z.string().nullable().optional(),
  status: z.string(),
  source_package_id: z.string().nullable().optional(),
  source_project_key: z.string().nullable().optional(),
  localized_content: z.record(z.string(), z.unknown()).optional(),
  primary_target_id: z.string().nullable(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type Project = z.infer<typeof ProjectSchema>

export const ProjectLibraryItemSchema = ProjectSchema.extend({
  research_candidate_count: z.number().default(0),
  finding_count: z.number().default(0),
  reference_count: z.number().default(0),
  knowledge_count: z.number().default(0),
  structure_count: z.number().default(0),
  primary_structure_ready: z.boolean().default(false),
  package_version: z.string().nullable().optional(),
  evidence_as_of: z.string().nullable().optional(),
})

export type ProjectLibraryItem = z.infer<typeof ProjectLibraryItemSchema>

export const ProjectOverviewSchema = z.object({
  project: ProjectSchema,
  funnel: z.object({
    generated: z.number(),
    designed: z.number(),
    folded: z.number(),
    scored: z.number(),
    ordered: z.number(),
  }),
  candidate_count: z.number(),
  experiment_result_count: z.number(),
  available_artifact_count: z.number(),
  active_job_count: z.number(),
  latest_workflow_id: z.string().nullable(),
  target_readiness: TargetReadinessSchema,
  next_action: z.string(),
})

export type ProjectOverview = z.infer<typeof ProjectOverviewSchema>
