import { z } from 'zod'

export const CandidateSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  candidate_key: z.string(),
  name: z.string(),
  candidate_kind: z.enum(['design_candidate', 'research_target']).optional(),
  status: z.string(),
  rank: z.number().nullable(),
  score: z.number().nullable(),
  scores: z.record(z.string(), z.unknown()),
  properties: z.record(z.string(), z.unknown()),
  structure_artifact_id: z.string().nullable(),
  complex_artifact_id: z.string().nullable(),
  source_job_id: z.string().nullable(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type Candidate = z.infer<typeof CandidateSchema>

export function candidateScore(candidate: Candidate, key: string): number | null {
  const value = candidate.scores[key]
  return typeof value === 'number' ? value : null
}

export function candidateText(candidate: Candidate, key: string): string | null {
  const value = candidate.properties[key] ?? candidate.scores[key]
  return typeof value === 'string' ? value : null
}

export function candidateStrings(candidate: Candidate, key: string): string[] {
  const value = candidate.properties[key]
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

export function resolveActiveCandidate(
  visibleCandidates: Candidate[],
  selectedCandidate: Candidate | null,
): Candidate | null {
  if (selectedCandidate) {
    const currentCandidate = visibleCandidates.find(
      (candidate) => candidate.id === selectedCandidate.id,
    )
    if (currentCandidate) return currentCandidate
  }
  return visibleCandidates[0] ?? null
}

export const CandidateListSchema = z.object({
  items: z.array(CandidateSchema),
  next_cursor: z.string().nullable().optional(),
})

export type CandidateListResponse = z.infer<typeof CandidateListSchema>

export const CandidateMetricSchema = z.object({
  id: z.string(),
  metric_key: z.string(),
  value: z.number(),
  method: z.string(),
  model_variant: z.string(),
  evidence_kind: z.string(),
  assessor: z.string(),
  condition: z.string(),
  unit: z.string(),
  context: z.record(z.string(), z.unknown()),
  source_job_id: z.string().nullable(),
  created_at: z.string(),
})

export type CandidateMetric = z.infer<typeof CandidateMetricSchema>

export const CandidateMetricListSchema = z.object({
  items: z.array(CandidateMetricSchema),
})

export type CandidateMetricListResponse = z.infer<typeof CandidateMetricListSchema>

export interface CandidateMetricGroup {
  metricKey: string
  rows: CandidateMetric[]
  /** Populated only when the group spans exactly two distinct non-empty conditions. */
  delta: { conditionA: string; conditionB: string; value: number; unit: string } | null
  /**
   * Populated when the same metric carries both a model's number and a bench number.
   *
   * This is the one comparison the dry and wet halves exist to produce, and it was
   * invisible: the panel grouped by metric key and showed condition and assessor, so a
   * measured Kd and a predicted Kd rendered as two identical-looking rows. Requires a
   * shared unit - "predicted 12 nM vs measured 40 µM" is not a delta, it is a mistake.
   */
  predictedVsMeasured: {
    predicted: CandidateMetric
    measured: CandidateMetric
    delta: number
    unit: string
  } | null
}

/** What produced a number. `measured` is only ever a real observation. */
export const MEASURED = 'measured'
export const PREDICTED = 'predicted'

function newest(rows: CandidateMetric[]): CandidateMetric | undefined {
  // Latest wins: a re-run supersedes, and re-analysing a bench file appends a row
  // rather than rewriting one, so the newest measured value is the current one.
  return rows.slice().sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
}

export function groupCandidateMetricsByKey(metrics: CandidateMetric[]): CandidateMetricGroup[] {
  const byKey = new Map<string, CandidateMetric[]>()
  for (const metric of metrics) {
    const rows = byKey.get(metric.metric_key) ?? []
    rows.push(metric)
    byKey.set(metric.metric_key, rows)
  }
  return Array.from(byKey.entries()).map(([metricKey, rows]) => {
    const distinctConditions = Array.from(new Set(rows.map((row) => row.condition).filter(Boolean)))
    const delta = distinctConditions.length === 2
      ? (() => {
          const a = rows.find((row) => row.condition === distinctConditions[0])
          const b = rows.find((row) => row.condition === distinctConditions[1])
          if (!a || !b || a.unit !== b.unit) return null
          return { conditionA: a.condition, conditionB: b.condition, value: a.value - b.value, unit: a.unit }
        })()
      : null
    const predicted = newest(rows.filter((row) => row.evidence_kind === PREDICTED))
    const measured = newest(rows.filter((row) => row.evidence_kind === MEASURED))
    const predictedVsMeasured =
      predicted && measured && predicted.unit === measured.unit
        ? { predicted, measured, delta: measured.value - predicted.value, unit: measured.unit }
        : null
    return { metricKey, rows, delta, predictedVsMeasured }
  })
}

export const ExperimentResultSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  candidate_id: z.string().nullable(),
  candidate_ref: z.string().nullable(),
  source_artifact_id: z.string().nullable(),
  batch_key: z.string().nullable(),
  experiment_type: z.string(),
  pass_status: z.string(),
  value: z.number().nullable(),
  unit: z.string().nullable(),
  conclusion: z.string().nullable(),
  failure_reason: z.string().nullable(),
  result_metadata: z.record(z.string(), z.unknown()),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type ExperimentResult = z.infer<typeof ExperimentResultSchema>

export type { Project } from './project'
export { ProjectSchema } from './project'
export type { WorkflowNode } from './workflow'
export { WorkflowNodeSchema } from './workflow'
