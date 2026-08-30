import { z } from 'zod'

export const DeliveryPackageSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  status: z.string(),
  name: z.string(),
  selection: z.record(z.string(), z.unknown()),
  artifact_id: z.string().nullable(),
  error: z.string().nullable(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type DeliveryPackageData = z.infer<typeof DeliveryPackageSchema>

export const ResultsSummarySchema = z.object({
  project_id: z.string(),
  candidate_count: z.number(),
  experiment_result_count: z.number(),
  available_artifact_count: z.number(),
  tested_candidate_count: z.number(),
  passed_result_count: z.number(),
  failed_result_count: z.number(),
  unknown_result_count: z.number(),
  pass_rate: z.number().nullable(),
  top_candidate_ids: z.array(z.string()),
  best_result_id: z.string().nullable(),
  best_result_value: z.number().nullable(),
  best_result_unit: z.string().nullable(),
})

export type ResultsSummary = z.infer<typeof ResultsSummarySchema>

export const CandidateFunnelSchema = z.object({
  generated: z.number(),
  designed: z.number(),
  folded: z.number(),
  scored: z.number(),
  ordered: z.number(),
})

export type CandidateFunnel = z.infer<typeof CandidateFunnelSchema>
