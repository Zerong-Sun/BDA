import { z } from 'zod'
import { ArtifactSchema } from './artifact'

export const TargetSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  name: z.string(),
  sequence: z.string().nullable(),
  uniprot_accession: z.string().nullable(),
  organism: z.string().nullable(),
  identity_status: z.string(),
  structure_artifact_id: z.string().nullable(),
  structure_status: z.string(),
  // A small-molecule target is identified by its chemistry and needs no uploaded
  // structure; its coordinates come from the component library when the job runs.
  target_kind: z.enum(['protein', 'small_molecule']).default('protein'),
  chemical_identity: z.record(z.string(), z.unknown()).default({}),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type Target = z.infer<typeof TargetSchema>

export const TargetStructureRevisionSchema = z.object({
  id: z.string(),
  target_id: z.string(),
  source_artifact_id: z.string(),
  prepared_artifact_id: z.string().nullable(),
  options: z.record(z.string(), z.unknown()),
  status: z.string(),
  approved: z.boolean(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type TargetStructureRevision = z.infer<typeof TargetStructureRevisionSchema>

export const TargetStructureViewSchema = z.object({
  target_id: z.string(),
  structure_status: z.string(),
  current_artifact_id: z.string().nullable(),
  approved_revision_id: z.string().nullable(),
  latest_revision: TargetStructureRevisionSchema.nullable(),
})

export const ProjectTargetStructureSchema = z.object({
  target: TargetSchema,
  structure: TargetStructureViewSchema,
  artifact: ArtifactSchema.nullable(),
})

export type ProjectTargetStructure = z.infer<typeof ProjectTargetStructureSchema>

export const TargetReadinessSchema = z.object({
  stage: z.string(),
  ready_for_workflow: z.boolean(),
  blockers: z.array(z.string()),
  next_action: z.string(),
  target_id: z.string().nullable(),
  structure_artifact_id: z.string().nullable(),
  identity_status: z.string().nullable(),
  structure_status: z.string().nullable(),
})

export type TargetReadiness = z.infer<typeof TargetReadinessSchema>
