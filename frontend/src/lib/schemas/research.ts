import { z } from 'zod'

export const ResearchBriefSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  title: z.string(),
  content: z.string(),
  scope: z.record(z.string(), z.unknown()),
  status: z.string(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export const ResearchFindingSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  brief_id: z.string().nullable(),
  finding_type: z.string(),
  title: z.string(),
  content: z.string(),
  evidence: z.record(z.string(), z.unknown()),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
  // How the question resolved. 'refuted' is a result, not a failure state.
  outcome: z.enum(['supported', 'refuted', 'inconclusive', 'unspecified']).default('unspecified'),
  supersedes_id: z.string().nullable().default(null),
  provenance: z.record(z.string(), z.unknown()).default({}),
})

export type ResearchFinding = z.infer<typeof ResearchFindingSchema>
export type FindingOutcome = ResearchFinding['outcome']

export const ProjectResearchSummarySchema = z.object({
  brief: ResearchBriefSchema.nullable(),
  findings: z.array(ResearchFindingSchema),
  literature_document_count: z.number(),
  intelligence_run_count: z.number(),
  knowledge_entry_count: z.number(),
})

export type ProjectResearchSummary = z.infer<typeof ProjectResearchSummarySchema>

export interface ProjectReviewSection {
  track: string
  label: string
  status: string
  items: ResearchFinding[]
}
