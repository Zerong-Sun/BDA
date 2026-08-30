import { z } from 'zod'
import type {
  JobResponse,
  SubmissionResponse,
  WorkflowNodeResponse,
  WorkflowResponse,
} from '../api/generated/types.gen'

/**
 * These used to be `z.string()`, which shadowed the generated contract: the app read
 * this loose type instead of the SDK's, so the workflow page could gate on 'completed'
 * - a status the API has never returned - without tsc or the SDK-drift check noticing.
 *
 * `satisfies` proves every value below still exists in the contract; `StatusesInSync`
 * proves the contract has no value missing here. Regenerating the SDK after a backend
 * enum change now breaks this file instead of silently leaving a dead branch behind.
 */
type Equals<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false
type Expect<T extends true> = T

export const WorkflowRunStatusSchema = z.enum([
  'draft',
  'queued',
  'running',
  'succeeded',
  'failed',
  'cancelled',
] as const satisfies readonly WorkflowResponse['status'][])

export const WorkflowNodeStatusSchema = z.enum([
  'draft',
  'pending',
  'dispatching',
  'queued',
  'running',
  'collecting',
  'succeeded',
  'failed',
  'cancelled',
  'requires_review',
] as const satisfies readonly WorkflowNodeResponse['status'][])

export const SubmitStatusSchema = z.enum([
  'pending',
  'running',
  'succeeded',
  'failed',
  'cancelled',
] as const satisfies readonly SubmissionResponse['status'][])

export const JobStatusSchema = z.enum([
  'pending',
  'dispatching',
  'queued',
  'running',
  'collecting',
  'succeeded',
  'failed',
  'cancelled',
] as const satisfies readonly JobResponse['status'][])

export type StatusesInSync = [
  Expect<Equals<z.infer<typeof WorkflowRunStatusSchema>, WorkflowResponse['status']>>,
  Expect<Equals<z.infer<typeof WorkflowNodeStatusSchema>, WorkflowNodeResponse['status']>>,
  Expect<Equals<z.infer<typeof SubmitStatusSchema>, SubmissionResponse['status']>>,
  Expect<Equals<z.infer<typeof JobStatusSchema>, JobResponse['status']>>,
]

/** Runs that can no longer change, so the editor must be read-only. */
export const TERMINAL_WORKFLOW_RUN_STATUSES = ['succeeded', 'failed', 'cancelled'] as const

export function isTerminalWorkflowRun(status: string | undefined): boolean {
  return (TERMINAL_WORKFLOW_RUN_STATUSES as readonly string[]).includes(status ?? '')
}

/** Jobs that have stopped. Everything else the server will accept a cancel for. */
export const TERMINAL_JOB_STATUSES = ['succeeded', 'failed', 'cancelled'] as const

export function isCancellableJob(status: string | undefined): boolean {
  if (!status) return false
  return !(TERMINAL_JOB_STATUSES as readonly string[]).includes(status)
}

const JsonRecordSchema = z.record(z.string(), z.unknown())
const PositionSchema = z.object({ x: z.number(), y: z.number() }).passthrough()

/** Where one input port of a node gets its data from. */
export const WorkflowInputBindingSchema = z.object({
  port: z.string(),
  source: z.enum(['artifact', 'upstream']),
  artifact_id: z.string().nullable().optional(),
  from_node: z.string().nullable().optional(),
  from_port: z.string().nullable().optional(),
}).passthrough()

export type WorkflowInputBinding = z.infer<typeof WorkflowInputBindingSchema>

export const WorkflowNodeSchema = z.object({
  id: z.string(),
  workflow_run_id: z.string(),
  node_key: z.string(),
  node_type: z.string(),
  model_plugin: z.string(),
  model_plugin_id: z.string().nullable(),
  container_image: z.string().nullable(),
  command: z.string().nullable(),
  queue: z.string().nullable(),
  status: WorkflowNodeStatusSchema,
  parameters: JsonRecordSchema,
  input_bindings: z.array(WorkflowInputBindingSchema).default([]),
  error_message: z.string().nullable(),
  position: PositionSchema.nullable().optional(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type WorkflowNode = z.infer<typeof WorkflowNodeSchema>
export type WorkflowRunStatus = z.infer<typeof WorkflowRunStatusSchema>
export type WorkflowNodeStatus = z.infer<typeof WorkflowNodeStatusSchema>
export type SubmitStatus = z.infer<typeof SubmitStatusSchema>

export const WorkflowEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  source_port: z.string().nullable().optional(),
  target_port: z.string().nullable().optional(),
}).passthrough()

export type WorkflowEdge = z.infer<typeof WorkflowEdgeSchema>

// A parameter that differs between this run and the one it derives from.
export const ParameterChangeSchema = z.object({ from: z.unknown(), to: z.unknown() })

export const WorkflowRunSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  name: z.string(),
  status: WorkflowRunStatusSchema,
  graph: JsonRecordSchema,
  version: z.number().int(),
  created_by: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  derived_from_id: z.string().nullable().default(null),
  // Computed by the platform at submission, not supplied by the author.
  arm_label: z.enum(['baseline', 'replicate', 'variant']).default('baseline'),
  varied_parameters: z.record(z.string(), z.record(z.string(), ParameterChangeSchema)).default({}),
})

export type WorkflowRun = z.infer<typeof WorkflowRunSchema>

export const WorkflowGraphSchema = z.object({
  workflow: WorkflowRunSchema,
  nodes: z.array(WorkflowNodeSchema),
  edges: z.array(WorkflowEdgeSchema),
  layout: JsonRecordSchema,
})

export type WorkflowGraph = z.infer<typeof WorkflowGraphSchema>

// Field names follow what preflight actually emits. An earlier `workflow_node_id` was
// never sent by any blocker, so the node hint the UI tried to render was always empty and
// every blocker read as a context-free sentence with no clue which stage produced it.
export const WorkflowPreflightIssueSchema = z.object({
  code: z.string(),
  message: z.string(),
  node_key: z.string().optional(),
  node_id: z.string().optional(),
  // Plugin-level issues are reported once per declaration, not per node. ``plugin_id``
  // identifies the exact version an admin must validate; keys are not unique over time.
  plugin_key: z.string().optional(),
  plugin_id: z.string().optional(),
  plugin_version: z.string().optional(),
  port: z.string().optional(),
}).passthrough()

export const WorkflowPreflightSchema = z.object({
  workflow_run_id: z.string(),
  allowed: z.boolean(),
  blockers: z.array(WorkflowPreflightIssueSchema),
  warnings: z.array(WorkflowPreflightIssueSchema),
  checks: JsonRecordSchema,
})

export type WorkflowPreflight = z.infer<typeof WorkflowPreflightSchema>

export const WorkflowLayoutSchema = z.object({
  nodes: z.array(z.object({ id: z.string(), position: PositionSchema })),
  edges: z.array(WorkflowEdgeSchema),
})

export type WorkflowLayout = z.infer<typeof WorkflowLayoutSchema>

/** Only a job that has stopped badly can be retried; the server enforces the same set. */
export function isRetryableJob(status: string | undefined): boolean {
  return status === 'failed' || status === 'cancelled'
}
