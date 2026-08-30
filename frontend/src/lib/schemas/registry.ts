import { z } from 'zod'

// A plugin declares what it consumes and produces. Ports are what let the workflow
// canvas offer a real choice of sources for each input instead of guessing.
export const InputPortSchema = z.object({
  name: z.string(),
  kind: z.string(),
  accepts: z.array(z.string()).default([]),
  content_types: z.array(z.string()).default([]),
  required: z.boolean().default(false),
  multiple: z.boolean().default(false),
  description: z.string().default(''),
  /** Ports sharing a group are alternatives; exactly one is bound. */
  exclusive_group: z.string().nullable().default(null),
}).passthrough()
export type InputPort = z.infer<typeof InputPortSchema>

export const OutputPortSchema = z.object({
  name: z.string(),
  kind: z.string(),
  artifact_type: z.string(),
  filename_glob: z.string().default('*'),
  description: z.string().default(''),
}).passthrough()
export type OutputPort = z.infer<typeof OutputPortSchema>

export const ModelPluginSchema = z.object({
  id: z.string(), plugin_key: z.string(), plugin_version: z.string(), name: z.string(),
  container_image: z.string(), command: z.string(), parameter_schema: z.record(z.string(), z.unknown()),
  output_schema: z.record(z.string(), z.unknown()), enabled: z.boolean(), validation_status: z.string(),
  validated_at: z.string().nullable(), validation_errors: z.array(z.unknown()), version: z.number(),
  created_at: z.string(), updated_at: z.string(),
  input_ports: z.array(InputPortSchema).default([]),
  output_ports: z.array(OutputPortSchema).default([]),
  resources: z.record(z.string(), z.unknown()).default({}),
  runtime_mode: z.string().default('container'),
  output_parser: z.string().nullable().default(null),
  input_adapter: z.string().nullable().default(null),
  runtime_validation_status: z.string().default('unproven'),
  runtime_validated_at: z.string().nullable().default(null),
  runtime_validation_evidence: z.record(z.string(), z.unknown()).default({}),
})
export type ModelPlugin = z.infer<typeof ModelPluginSchema>

export const MethodPluginSchema = z.object({
  id: z.string(), plugin_key: z.string(), name: z.string(), specification: z.record(z.string(), z.unknown()),
  enabled: z.boolean(), version: z.number(), created_at: z.string(), updated_at: z.string(),
})
export type MethodPlugin = z.infer<typeof MethodPluginSchema>

export const ComputeNodeSchema = z.object({
  id: z.string(), server_id: z.string().nullable(), name: z.string(), backend: z.string(), queue: z.string().nullable(),
  labels: z.record(z.string(), z.unknown()), enabled: z.boolean(), health_status: z.string(),
  health_checked_at: z.string().nullable(), health_error: z.string().nullable(), version: z.number(),
  created_at: z.string(), updated_at: z.string(),
})
export type ComputeNode = z.infer<typeof ComputeNodeSchema>

export const ServerConnectionSchema = z.object({
  id: z.string(), name: z.string(), server_type: z.string(), endpoint: z.string(), enabled: z.boolean(),
  health_status: z.string(), health_checked_at: z.string().nullable(), health_error: z.string().nullable(),
  version: z.number(), created_at: z.string(), updated_at: z.string(),
})
export type ServerConnection = z.infer<typeof ServerConnectionSchema>

export const ScriptAssetSchema = z.object({
  id: z.string(), name: z.string(), artifact_id: z.string(), checksum_sha256: z.string(), runtime: z.string(),
  created_by: z.string(), version: z.number(), created_at: z.string(), updated_at: z.string(),
})
export type ScriptAsset = z.infer<typeof ScriptAssetSchema>

export const ScriptUploadResultSchema = z.object({
  success: z.boolean(),
  item: z.object({
    id: z.string(), artifact_id: z.string(), name: z.string(), checksum_sha256: z.string(), runtime: z.string(),
    parameter_observations: z.number(), parse_warnings: z.number(), warnings: z.array(z.string()),
  }),
})
export type ScriptUploadResult = z.infer<typeof ScriptUploadResultSchema>
