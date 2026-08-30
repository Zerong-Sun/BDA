import './generatedTransport'
import { uploadArtifact } from './artifacts'
import {
  checkComputeNodeApiV2RegistryComputeNodesNodeIdHealthChecksPost,
  createMethodPluginApiV2RegistryMethodPluginsPost,
  createComputeNodeApiV2RegistryComputeNodesPost,
  createScriptAssetApiV2RegistryScriptAssetsPost,
  disableComputeNodeApiV2RegistryComputeNodesNodeIdDelete,
  listComputeNodesApiV2RegistryComputeNodesGet,
  listMethodPluginsApiV2RegistryMethodPluginsGet,
  listModelPluginsApiV2RegistryModelPluginsGet,
  listScriptAssetsApiV2RegistryScriptAssetsGet,
  listServersApiV2RegistryServersGet,
  testServerConnectionApiV2RegistryServersServerIdConnectionTestsPost,
  validateModelPluginApiV2RegistryModelPluginsPluginIdValidationsPost,
} from './generated/sdk.gen'
import {
  ComputeNodeSchema,
  MethodPluginSchema,
  ModelPluginSchema,
  ScriptAssetSchema,
  ScriptUploadResultSchema,
  ServerConnectionSchema,
  type ComputeNode,
  type MethodPlugin,
  type ModelPlugin,
  type ScriptAsset,
  type ScriptUploadResult,
  type ServerConnection,
} from '../schemas/registry'

export async function listModelPlugins(): Promise<ModelPlugin[]> {
  const response = await listModelPluginsApiV2RegistryModelPluginsGet<true>({
    query: { limit: 200 }, throwOnError: true,
  })
  return response.data.items.map((item) => ModelPluginSchema.parse(item))
}

export async function listMethodPlugins(): Promise<MethodPlugin[]> {
  const response = await listMethodPluginsApiV2RegistryMethodPluginsGet<true>({
    query: { limit: 200 }, throwOnError: true,
  })
  return response.data.items.map((item) => MethodPluginSchema.parse(item))
}

export interface CreateMethodPluginPayload {
  method_name: string
  method_type?: string
  description?: string | null
  input_schema_json?: Record<string, unknown>
  output_schema_json?: Record<string, unknown>
  parameter_schema_json?: Record<string, unknown>
  compatible_model_types?: string[]
  compatible_workflow_nodes?: string[]
  default_parameters_json?: Record<string, unknown>
  version?: string
  status?: 'active' | 'experimental' | 'disabled'
}

export async function createMethodPlugin(payload: CreateMethodPluginPayload): Promise<MethodPlugin> {
  const response = await createMethodPluginApiV2RegistryMethodPluginsPost<true>({
    body: { plugin_key: payload.method_name.toLowerCase().replace(/\s+/g, '-'),
      name: payload.method_name, specification: { ...payload }, enabled: payload.status !== 'disabled' },
    throwOnError: true,
  })
  return MethodPluginSchema.parse(response.data)
}

export async function listComputeNodes(): Promise<ComputeNode[]> {
  const response = await listComputeNodesApiV2RegistryComputeNodesGet<true>({
    query: { limit: 200 }, throwOnError: true,
  })
  return response.data.items.map((item) => ComputeNodeSchema.parse(item))
}

export interface ClusterHealth {
  mode: string
  connected: boolean
  host?: string
  remote_root?: string
  queues: string[]
  all_queues?: string[]
  reason?: string | null
}

export function getClusterHealth(): Promise<ClusterHealth> {
  return listComputeNodes().then((nodes) => ({ mode: 'registry', connected: nodes.some((node) => node.enabled && node.health_status !== 'unhealthy'),
    queues: [], reason: nodes.length ? null : 'No compute nodes are registered' }))
}

export async function listServers(): Promise<ServerConnection[]> {
  const response = await listServersApiV2RegistryServersGet<true>({
    query: { limit: 200 }, throwOnError: true,
  })
  return response.data.items.map((item) => ServerConnectionSchema.parse(item))
}

export interface CreateComputeNodePayload {
  name: string
  backend: string
  queue?: string | null
  server_id?: string | null
  labels?: Record<string, unknown>
}

/**
 * Register somewhere the platform can dispatch to.
 *
 * Admin-only on the server. Until this existed, a deployment could only learn about a
 * cluster through a migration or a script, so the settings drawer could report "no
 * compute nodes are registered" without offering any way to fix it.
 */
export async function createComputeNode(payload: CreateComputeNodePayload): Promise<ComputeNode> {
  const response = await createComputeNodeApiV2RegistryComputeNodesPost<true>({
    body: { labels: {}, enabled: true, ...payload },
    throwOnError: true,
  })
  return ComputeNodeSchema.parse(response.data)
}

/** Disabling keeps the row and its history; the scheduler simply stops choosing it. */
export function disableComputeNode(computeNodeId: string, version: number) {
  return disableComputeNodeApiV2RegistryComputeNodesNodeIdDelete<true>({
    path: { node_id: computeNodeId },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  }).then((response) => response.data)
}

export function checkComputeNodeHealth(computeNodeId: string) {
  return checkComputeNodeApiV2RegistryComputeNodesNodeIdHealthChecksPost<true>({
    path: { node_id: computeNodeId }, throwOnError: true,
  }).then((response) => response.data)
}

export function validateModelPlugin(modelPluginId: string) {
  return validateModelPluginApiV2RegistryModelPluginsPluginIdValidationsPost<true>({
    path: { plugin_id: modelPluginId }, throwOnError: true,
  }).then((response) => response.data)
}

export async function listScriptAssets(modelPluginId?: string): Promise<ScriptAsset[]> {
  void modelPluginId
  const response = await listScriptAssetsApiV2RegistryScriptAssetsGet<true>({
    query: { limit: 200 }, throwOnError: true,
  })
  return response.data.items.map((item) => ScriptAssetSchema.parse(item))
}

export function uploadScriptAsset(
  file: File,
  options: { modelPluginId?: string; relativePath?: string; projectId?: string } = {},
): Promise<ScriptUploadResult> {
  if (!options.projectId) return Promise.reject(new Error('A project is required for script uploads.'))
  return uploadArtifact(file, options.projectId).then(async (artifact) => {
    const response = await createScriptAssetApiV2RegistryScriptAssetsPost<true>({
      body: { name: options.relativePath || file.name, artifact_id: artifact.id, runtime: 'shell' },
      throwOnError: true,
    })
    const item = response.data
    return ScriptUploadResultSchema.parse({ success: true, item: { id: item.id,
      artifact_id: artifact.id, name: options.relativePath || file.name,
      checksum_sha256: item.checksum_sha256, runtime: 'shell',
      parameter_observations: 0, parse_warnings: 0, warnings: [] } })
  })
}

export function testServerConnection(serverId: string) {
  return testServerConnectionApiV2RegistryServersServerIdConnectionTestsPost<true>({
    path: { server_id: serverId }, throwOnError: true,
  }).then((response) => response.data)
}
