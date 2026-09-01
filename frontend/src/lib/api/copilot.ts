import { API_BASE, ApiError } from './client'
import './generatedTransport'
import {
  createInterpretationApiV2CopilotInterpretationsPost,
  createRoutePlanApiV2CopilotRoutePlansPost,
  confirmComputeDraftApiV2ComputeDraftsDraftIdConfirmPost,
  deleteEntryApiV2KnowledgeEntryIdDelete,
  detectRelationsApiV2ProjectsProjectIdLiteratureRelationDetectionsPost,
  getCandidateApiV2CandidatesCandidateIdGet,
  getClaimApiV2LiteratureClaimsClaimIdGet,
  getComputeDraftApiV2ComputeDraftsDraftIdGet,
  getConfigApiV2CopilotProjectsProjectIdConfigGet,
  getEvidenceApiV2IntelligenceEvidenceEvidenceIdGet,
  getHotspotApiV2IntelligenceHotspotsHotspotIdGet,
  getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet,
  getWorkflowGraphApiV2WorkflowRunsWorkflowIdGraphGet,
  getRelationApiV2LiteratureRelationsRelationIdGet,
  getRunApiV2IntelligenceRunsRunIdGet,
  getSubscriptionApiV2LiteratureSubscriptionsSubscriptionIdGet,
  listClaimsApiV2ProjectsProjectIdLiteratureClaimsGet,
  listComputeDraftsApiV2ComputeDraftsGet,
  listDocumentsApiV2ProjectsProjectIdLiteratureDocumentsGet,
  listEntriesApiV2ProjectsProjectIdKnowledgeGet,
  listModelPluginsApiV2RegistryModelPluginsGet,
  listRelationsApiV2ProjectsProjectIdLiteratureRelationsGet,
  listSearchesApiV2ProjectsProjectIdLiteratureSearchesGet,
  listSubscriptionsApiV2ProjectsProjectIdLiteratureSubscriptionsGet,
  patchEntryApiV2KnowledgeEntryIdPatch,
  patchSubscriptionApiV2LiteratureSubscriptionsSubscriptionIdPatch,
  postApplyRouteApiV2DesignRoutesRouteIdApplyPost,
  postChatApiV2CopilotChatPost,
  postEntryApiV2ProjectsProjectIdKnowledgePost,
  postExportApiV2IntelligenceRunsRunIdExportsPost,
  postSearchApiV2ProjectsProjectIdLiteratureSearchesPost,
  postRunApiV2ProjectsProjectIdIntelligenceRunsPost,
  postSubscriptionApiV2ProjectsProjectIdLiteratureSubscriptionsPost,
  postWorkflowApiV2ProjectsProjectIdWorkflowRunsPost,
  putConfigApiV2CopilotProjectsProjectIdConfigPut,
  reviewClaimApiV2LiteratureClaimsClaimIdPatch,
  reviewEvidenceApiV2IntelligenceEvidenceEvidenceIdPatch,
  reviewHotspotApiV2IntelligenceHotspotsHotspotIdPatch,
  reviewRelationApiV2LiteratureRelationsRelationIdPatch,
  runSubscriptionApiV2LiteratureSubscriptionsSubscriptionIdRunsPost,
  testConfigApiV2CopilotProjectsProjectIdConfigTestsPost,
} from './generated/sdk.gen'
import { z } from 'zod'

export interface CopilotMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface CopilotChatRequest {
  messages: CopilotMessage[]
  project_id?: string
  skill?: string
  conversation_id?: string | null
  intent?: 'chat' | 'review_section'
  context?: {
    route?: string
    research_tab?: string
    selected_entity_ids?: string[]
    language?: 'en' | 'zh'
  }
}

export interface CopilotStreamMessage {
  id?: string
  content: string
  citations: Array<Record<string, unknown>>
  tool_calls: Array<Record<string, unknown>>
}

/** Strip UI-only fields and drop empty messages before hitting the API schema. */
export function toCopilotApiMessages(
  messages: Array<{ role: CopilotMessage['role']; content: string; meta?: unknown }>,
): CopilotMessage[] {
  return messages
    .filter((message) => message.content.trim().length > 0)
    .map((message) => ({ role: message.role, content: message.content.trim() }))
}

export const CopilotChatResponseSchema = z.object({
  mode: z.string(),
  message: z.string(),
  skill_used: z.string().optional(),
  structured: z.record(z.string(), z.unknown()).optional(),
})

export type CopilotChatResponse = z.infer<typeof CopilotChatResponseSchema>

export const CopilotConfigSchema = z.object({
  llm_api_base: z.string(),
  llm_model: z.string(),
  api_key_configured: z.boolean(),
  api_key_preview: z.string().nullable().optional(),
  system_scope: z.string(),
  system_prompt: z.string(),
  version: z.number().optional(),
  llm_provider_id: z.string().nullable().optional(),
  //: Read back so a settings save can preserve it. Saving used to send a
  //: hard-coded list, which silently revoked every capability added after that
  //: list was written - the bench tools and agent orchestration among them.
  enabled_skills: z.array(z.string()).default([]),
})

export type CopilotConfig = z.infer<typeof CopilotConfigSchema>

export const CopilotKnowledgeEntrySchema = z.object({
  knowledge_entry_id: z.string(),
  title: z.string(),
  category: z.string(),
  subcategory: z.string().nullable().optional(),
  summary: z.string(),
  content: z.string(),
  tags_json: z.array(z.string()).optional(),
  related_model_plugins: z.array(z.string()).optional(),
  related_method_plugins: z.array(z.string()).optional(),
  source_type: z.string(),
  citation: z.string().nullable().optional(),
  confidence: z.string(),
  metadata_json: z.record(z.string(), z.unknown()).optional(),
  status: z.string(),
  version: z.number(),
})

export type CopilotKnowledgeEntry = z.infer<typeof CopilotKnowledgeEntrySchema>

export interface CopilotKnowledgeEntryUpsert {
  knowledge_entry_id?: string
  title: string
  category: string
  subcategory?: string
  summary: string
  content: string
  tags?: string[]
  related_model_plugins?: string[]
  related_method_plugins?: string[]
  source_type?: string
  citation?: string
  confidence?: string
  metadata?: Record<string, unknown>
}

export interface CopilotConfigUpdate {
  llm_api_base?: string
  llm_api_key?: string
  llm_model?: string
  system_prompt?: string
}

export const ClusterDraftSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  name: z.string(),
  backend: z.string(),
  specification: z.record(z.string(), z.unknown()),
  status: z.string(),
  confirmed_job_id: z.string().nullable(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type ClusterDraft = z.infer<typeof ClusterDraftSchema>

export function getCopilotConfig(projectId?: string) {
  if (!projectId) return Promise.resolve(CopilotConfigSchema.parse({ llm_api_base: '', llm_model: '',
    api_key_configured: false, system_scope: 'project', system_prompt: '' }))
  return getConfigApiV2CopilotProjectsProjectIdConfigGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  }).then(({ data: config }) => {
    const settings = config.settings ?? {}
    return CopilotConfigSchema.parse({ llm_api_base: settings.llm_api_base ?? '',
      llm_model: settings.llm_model ?? '', api_key_configured: config.api_key_configured,
      api_key_preview: settings.api_key_preview ?? null,
      system_scope: 'project', system_prompt: settings.system_prompt ?? '',
      enabled_skills: config.enabled_skills ?? [],
      version: config.version, llm_provider_id: config.llm_provider_id ?? null })
  })
}

export async function updateCopilotConfig(projectId: string, payload: CopilotConfigUpdate) {
  let current: CopilotConfig | null = null
  try {
    current = await getCopilotConfig(projectId)
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) throw error
  }
  await putConfigApiV2CopilotProjectsProjectIdConfigPut<true>({
    path: { project_id: projectId },
    headers: current?.version != null ? { 'If-Match': `W/"${current.version}"` } : undefined,
    body: { llm_provider_id: current?.llm_provider_id ?? null,
      settings: { llm_api_base: payload.llm_api_base, llm_model: payload.llm_model,
        system_prompt: payload.system_prompt ?? current?.system_prompt ?? '',
        ...(payload.llm_api_key ? { llm_api_key: payload.llm_api_key } : {}) },
      // Whatever the project already had. A hard-coded list here revoked every
      // capability added after it was written; "research" is the alias the
      // server expands to the full default set for a project that has none yet.
      enabled_skills: current?.enabled_skills?.length ? current.enabled_skills : ['research'] },
    throwOnError: true,
  })
  return getCopilotConfig(projectId)
}

export function testCopilotConfig(projectId: string) {
  return testConfigApiV2CopilotProjectsProjectIdConfigTestsPost<true>({
    path: { project_id: projectId }, throwOnError: true,
  }).then(({ data }) => ({ connected: data.connected, model: data.model,
    sample: data.sample ?? undefined, reason: data.reason ?? undefined }))
}

export async function listClusterDrafts(projectId?: string) {
  if (!projectId) return Promise.resolve({ items: [] as ClusterDraft[] })
  const response = await listComputeDraftsApiV2ComputeDraftsGet<true>({
    query: { project_id: projectId, limit: 200 }, throwOnError: true,
  })
  return { items: response.data.items.map((draft) => ClusterDraftSchema.parse(draft)) }
}

export async function getClusterDraft(draftId: string) {
  const response = await getComputeDraftApiV2ComputeDraftsDraftIdGet<true>({
    path: { draft_id: draftId }, throwOnError: true,
  })
  return ClusterDraftSchema.parse(response.data)
}

export function confirmClusterDraft(draftId: string) {
  return confirmComputeDraftApiV2ComputeDraftsDraftIdConfirmPost<true>({
    path: { draft_id: draftId }, throwOnError: true,
  }).then((response) => ClusterDraftSchema.parse(response.data))
}

export function searchCopilotKnowledge(projectId: string, query: string, category?: string) {
  return listEntriesApiV2ProjectsProjectIdKnowledgeGet<true>({
    path: { project_id: projectId }, query: { limit: 200 }, throwOnError: true,
  }).then(({ data: page }) => {
    const normalized = query.trim().toLowerCase()
    const items = page.items.filter((item) => !normalized || `${item.title} ${item.content}`.toLowerCase().includes(normalized))
      .filter((item) => !category || item.entry_type === category)
      .map((item) => CopilotKnowledgeEntrySchema.parse({ knowledge_entry_id: item.id, title: item.title,
        category: item.entry_type, summary: String(item.content).slice(0, 240), content: item.content,
        tags_json: item.tags, source_type: 'project', citation: '', confidence: 'curated', status: 'active',
        metadata_json: { version: item.version }, version: item.version }))
    return { items, next_cursor: page.next_cursor, query }
  })
}

export function createCopilotKnowledgeEntry(projectId: string, payload: CopilotKnowledgeEntryUpsert) {
  return postEntryApiV2ProjectsProjectIdKnowledgePost<true>({ path: { project_id: projectId }, body: {
    title: payload.title, content: payload.content, entry_type: payload.category,
    source: { type: payload.source_type, citation: payload.citation }, tags: payload.tags ?? [],
  }, throwOnError: true }).then(({ data: item }) => CopilotKnowledgeEntrySchema.parse({ knowledge_entry_id: item.id, title: item.title,
    category: item.entry_type, summary: payload.summary, content: item.content, tags_json: item.tags,
    source_type: payload.source_type ?? 'project', citation: payload.citation, confidence: payload.confidence ?? 'curated',
    status: 'active', metadata_json: { version: item.version }, version: item.version }))
}

export function updateCopilotKnowledgeEntry(entryId: string, payload: CopilotKnowledgeEntryUpsert, version: number) {
  return patchEntryApiV2KnowledgeEntryIdPatch<true>({ path: { entry_id: entryId },
    headers: { 'If-Match': `W/"${version}"` }, body: { title: payload.title, content: payload.content,
      entry_type: payload.category, source: { type: payload.source_type, citation: payload.citation }, tags: payload.tags ?? [] },
    throwOnError: true,
  }).then(({ data: item }) => CopilotKnowledgeEntrySchema.parse({ knowledge_entry_id: item.id, title: item.title,
    category: item.entry_type, summary: payload.summary, content: item.content, tags_json: item.tags,
    source_type: payload.source_type ?? 'project', citation: payload.citation, confidence: payload.confidence ?? 'curated',
    status: 'active', metadata_json: { version: item.version }, version: item.version }))
}

export function archiveCopilotKnowledgeEntry(entryId: string, version: number) {
  return deleteEntryApiV2KnowledgeEntryIdDelete<true>({ path: { entry_id: entryId },
    headers: { 'If-Match': `W/"${version}"` }, throwOnError: true })
}

export function ingestLiterature(projectId: string, query: string, limit = 5) {
  return postSearchApiV2ProjectsProjectIdLiteratureSearchesPost<true>({
    path: { project_id: projectId },
    body: {
      query,
      sources: ['europe_pmc'],
      limit,
      fetch_full_text: true,
      extract_claims: true,
    }, throwOnError: true,
  }).then(({ data }) => data)
}

export function listLiteratureSearches(projectId: string) {
  return listSearchesApiV2ProjectsProjectIdLiteratureSearchesGet<true>({
    path: { project_id: projectId },
    query: { limit: 50 },
    throwOnError: true,
  }).then(({ data }) => data)
}

export function searchLiteratureLibrary(projectId: string, query: string) {
  return listDocumentsApiV2ProjectsProjectIdLiteratureDocumentsGet<true>({
    path: { project_id: projectId }, query: { limit: 200 }, throwOnError: true,
  }).then(({ data: page }) => ({ ...page,
    items: page.items.filter((item) => !query.trim() || `${item.title} ${item.abstract ?? ''}`.toLowerCase().includes(query.trim().toLowerCase())),
  }))
}

export function listLiteratureClaims(projectId: string, reviewStatus?: 'accepted' | 'rejected' | 'pending_review') {
  return listClaimsApiV2ProjectsProjectIdLiteratureClaimsGet<true>({
    path: { project_id: projectId },
    query: { limit: 200, review_status: reviewStatus === 'pending_review' ? 'pending' : reviewStatus },
    throwOnError: true,
  }).then(({ data }) => data)
}

export function reviewLiteratureClaim(claimId: string, reviewStatus: 'accepted' | 'rejected') {
  return getClaimApiV2LiteratureClaimsClaimIdGet<true>({ path: { claim_id: claimId }, throwOnError: true })
    .then(({ data: current }) => reviewClaimApiV2LiteratureClaimsClaimIdPatch<true>({ path: { claim_id: claimId },
      headers: { 'If-Match': `W/"${current.version}"` }, body: { review_status: reviewStatus }, throwOnError: true,
    }))
}

export function listLiteratureRelations(projectId: string, reviewStatus = 'pending_review') {
  return listRelationsApiV2ProjectsProjectIdLiteratureRelationsGet<true>({ path: { project_id: projectId },
    query: { limit: 200, review_status: reviewStatus === 'pending_review' ? 'pending' : reviewStatus }, throwOnError: true,
  }).then(({ data }) => data)
}

export function reviewLiteratureRelation(relationId: string, reviewStatus: 'accepted' | 'rejected') {
  return getRelationApiV2LiteratureRelationsRelationIdGet<true>({ path: { relation_id: relationId }, throwOnError: true })
    .then(({ data: current }) => reviewRelationApiV2LiteratureRelationsRelationIdPatch<true>({
      path: { relation_id: relationId }, headers: { 'If-Match': `W/"${current.version}"` },
      body: { review_status: reviewStatus }, throwOnError: true,
    }))
}

export function detectLiteratureRelations(projectId: string) {
  return detectRelationsApiV2ProjectsProjectIdLiteratureRelationDetectionsPost<true>({
    path: { project_id: projectId }, throwOnError: true,
  })
}

export interface LiteratureSubscription {
  subscription_id: string
  name: string
  query: string
  enabled: boolean
  interval_hours: number
  result_limit: number
  fetch_full_text: boolean
  extract_claims: boolean
  last_status?: string | null
  last_run_at?: string | null
  next_run_at: string
}

export function listLiteratureSubscriptions(projectId: string) {
  return listSubscriptionsApiV2ProjectsProjectIdLiteratureSubscriptionsGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  }).then(({ data: page }) => ({ items: page.items.map((item) => ({ ...item,
    subscription_id: item.id,
    name: item.query, interval_hours: item.cadence === 'daily' ? 24 : 168,
    result_limit: 5, fetch_full_text: true, extract_claims: true,
    next_run_at: item.updated_at })), next_cursor: page.next_cursor }))
}

export function createLiteratureSubscription(projectId: string, payload: Omit<LiteratureSubscription, 'subscription_id' | 'last_status' | 'last_run_at' | 'next_run_at'>) {
  return postSubscriptionApiV2ProjectsProjectIdLiteratureSubscriptionsPost<true>({ path: { project_id: projectId },
    body: { query: payload.query, cadence: payload.interval_hours === 24 ? 'daily' : 'weekly' }, throwOnError: true,
  }).then(({ data }) => ({ ...payload, ...data, subscription_id: data.id, name: data.query,
    next_run_at: data.updated_at }))
}

export function updateLiteratureSubscription(
  subscriptionId: string,
  payload: Omit<LiteratureSubscription, 'subscription_id' | 'last_status' | 'last_run_at' | 'next_run_at'>,
) {
  return getSubscriptionApiV2LiteratureSubscriptionsSubscriptionIdGet<true>({ path: { subscription_id: subscriptionId },
    throwOnError: true }).then(({ data: current }) =>
    patchSubscriptionApiV2LiteratureSubscriptionsSubscriptionIdPatch<true>({ path: { subscription_id: subscriptionId },
      headers: { 'If-Match': `W/"${current.version}"` }, body: { query: payload.query,
        cadence: payload.interval_hours === 24 ? 'daily' : 'weekly', enabled: payload.enabled }, throwOnError: true }),
  ).then(({ data }) => ({ ...payload, ...data, subscription_id: data.id, name: data.query, next_run_at: data.updated_at }))
}

export function runLiteratureSubscription(subscriptionId: string) {
  return runSubscriptionApiV2LiteratureSubscriptionsSubscriptionIdRunsPost<true>({
    path: { subscription_id: subscriptionId }, throwOnError: true,
  })
}

export function sendCopilotMessage(payload: CopilotChatRequest) {
  const body: CopilotChatRequest = {
    ...payload,
    messages: toCopilotApiMessages(payload.messages),
  }
  const message = body.messages.at(-1)?.content ?? ''
  if (!body.project_id) return Promise.reject(new Error('A project is required for Copilot.'))
  return postChatApiV2CopilotChatPost<true>({ body: {
    project_id: body.project_id, message,
    skill: body.skill,
    conversation_id: body.conversation_id ?? undefined,
    intent: body.intent ?? 'chat',
    context: {
      route: body.context?.route,
      research_tab: body.context?.research_tab,
      selected_entity_ids: body.context?.selected_entity_ids ?? [],
      language: body.context?.language ?? 'en',
    },
  }, throwOnError: true })
    .then(({ data: accepted }) => CopilotChatResponseSchema.parse({ mode: 'async', message: accepted.message.content,
    structured: { conversation_id: accepted.conversation_id, status: accepted.message.status } }))
}

export type CopilotStreamStatus = 'connecting' | 'thinking' | 'streaming' | 'done' | `tool:${string}`

let latestCopilotMode: string | null = null

export function getLatestCopilotMode(): string | null {
  return latestCopilotMode
}

export async function streamCopilotMessage(
  payload: CopilotChatRequest,
  onChunk: (text: string) => void,
  onStatus?: (status: CopilotStreamStatus) => void,
  onMessage?: (message: CopilotStreamMessage) => void,
): Promise<{ conversationId: string; messageId: string }> {
  const token = sessionStorage.getItem('bda_token')
  onStatus?.('connecting')
  const body: CopilotChatRequest = {
    ...payload,
    messages: toCopilotApiMessages(payload.messages),
  }
  if (!body.project_id) throw new Error('A project is required for Copilot.')
  const { data: accepted } = await postChatApiV2CopilotChatPost<true>({ body: {
    project_id: body.project_id, message: body.messages.at(-1)?.content ?? '',
    skill: body.skill,
    conversation_id: body.conversation_id ?? undefined,
    intent: body.intent ?? 'chat',
    context: {
      route: body.context?.route,
      research_tab: body.context?.research_tab,
      selected_entity_ids: body.context?.selected_entity_ids ?? [],
      language: body.context?.language ?? 'en',
    },
  }, throwOnError: true })
  const acceptedMessageId = accepted.message?.id ?? ''
  const streamQuery = acceptedMessageId ? `?after_message_id=${encodeURIComponent(acceptedMessageId)}` : ''
  const response = await fetch(`${API_BASE}/copilot/conversations/${accepted.conversation_id}/stream${streamQuery}`, {
    method: 'GET',
    headers: {
      'content-type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!response.ok || !response.body) {
    let detail = `Copilot connection failed (${response.status})`
    try {
      const payload = await response.json()
      detail = payload?.detail ?? payload?.message ?? detail
    } catch {
      // Keep the HTTP status reason when the server did not return JSON.
    }
    throw new Error(detail)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split(/\r?\n\r?\n/)
    buffer = events.pop() ?? ''
    for (const evt of events) {
      const lines = evt.split(/\r?\n/)
      const dataLines = lines.filter((line) => line.startsWith('data:'))
      const eventLine = lines.find((line) => line.startsWith('event:'))
      const eventName = eventLine?.slice(6).trim()
      const data = dataLines
        .map((line) => {
          const value = line.slice(5)
          return value.startsWith(' ') ? value.slice(1) : value
        })
        .join('\n')
      if (eventName === 'message') {
        onStatus?.('streaming')
        let chunk = data
        try {
          const message = JSON.parse(data) as { id?: unknown; role?: unknown; content?: unknown; citations?: unknown; tool_calls?: unknown }
          if (typeof message.role === 'string') {
            if (message.role !== 'assistant') continue
            chunk = typeof message.content === 'string' ? message.content : ''
            onMessage?.({
              id: typeof message.id === 'string' ? message.id : undefined,
              content: chunk,
              citations: Array.isArray(message.citations) ? message.citations as Array<Record<string, unknown>> : [],
              tool_calls: Array.isArray(message.tool_calls) ? message.tool_calls as Array<Record<string, unknown>> : [],
            })
          }
        } catch {
          // Older/demo SSE endpoints may stream plain text chunks.
        }
        if (chunk) onChunk(chunk)
      } else if (eventName === 'status') {
        if (data === 'connected') {
          onStatus?.('connecting')
        } else if (data === 'thinking') {
          onStatus?.('thinking')
        } else if (data.startsWith('tool:')) {
          onStatus?.(data as `tool:${string}`)
        } else if (data === 'streaming') {
          onStatus?.('streaming')
        }
      } else if (eventName === 'error') {
        throw new Error(data || 'Copilot request failed')
      } else if (eventName === 'done') {
        onStatus?.('done')
        try {
          const payload = JSON.parse(data)
          if (payload?.mode) {
            latestCopilotMode = String(payload.mode)
          }
        } catch {
          // Ignore malformed done payloads.
        }
      }
    }
  }
  return { conversationId: accepted.conversation_id, messageId: acceptedMessageId }
}

export const RouteModuleSchema = z.object({
  module_id: z.string(),
  model_plugin_id: z.string().nullable().optional(),
  model_name: z.string(),
  node_type: z.string(),
  available: z.boolean(),
  summary: z.string(),
  default_parameters: z.record(z.string(), z.unknown()).optional(),
  parameter_schema: z.record(z.string(), z.unknown()).or(z.unknown()).optional(),
}).passthrough()

export const RouteOptionSchema = z.object({
  route_id: z.string(),
  label: z.string(),
  rank: z.number(),
  recommended: z.boolean(),
  summary: z.string(),
  rationale: z.array(z.string()),
  modules: z.array(RouteModuleSchema),
  risks: z.array(z.string()),
  // Thresholds and limits the route carries from the project's methods document.
  constraints: z.record(z.string(), z.unknown()).default({}),
  estimated_steps: z.number(),
}).passthrough()

export const RoutePlanSchema = z.object({
  mode: z.string(),
  project_id: z.string().nullable().optional(),
  target: z.string(),
  objective: z.string(),
  constraints: z.record(z.string(), z.unknown()),
  knowledge_context: z.array(z.object({
    knowledge_entry_id: z.string(),
    title: z.string(),
    category: z.string(),
    summary: z.string(),
  })),
  analysis_trace: z.array(z.string()),
  route_options: z.array(RouteOptionSchema),
}).passthrough()

export const AppliedRoutePlanSchema = z.object({
  workflow_run: z.object({ id: z.string() }).passthrough(),
  nodes: z.array(z.object({ id: z.string() }).passthrough()),
  edges: z.array(z.object({ id: z.string() }).passthrough()),
  route: RouteOptionSchema,
  knowledge_context: RoutePlanSchema.shape.knowledge_context,
  analysis_trace: z.array(z.string()),
})

export const TargetIdentitySchema = z.object({
  name: z.string(),
  organism: z.string().nullable().optional(),
  uniprot_accession: z.string().nullable().optional(),
  gene_names: z.array(z.string()).optional(),
  sequence_length: z.number().nullable().optional(),
  reviewed: z.boolean().nullable().optional(),
  construct_recommendation: z.string().nullable().optional(),
  confidence: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
}).passthrough()

export const TargetEvidenceItemSchema = z.object({
  source_type: z.string(),
  identifier: z.string().nullable().optional(),
  title: z.string(),
  claim: z.string(),
  excerpt: z.string().nullable().optional(),
  url: z.string().nullable().optional(),
  claim_type: z.string(),
  evidence_level: z.string(),
  confidence: z.string(),
  review_status: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
}).passthrough()

export const TargetHotspotSchema = z.object({
  residue: z.string(),
  residue_index: z.number().nullable().optional(),
  chain_id: z.string().nullable().optional(),
  region: z.string(),
  rationale: z.string(),
  evidence_level: z.string(),
  confidence: z.string(),
  extraction_method: z.string().optional(),
  source_refs: z.array(z.string()).optional(),
  status: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
}).passthrough()

export const TargetDesignRouteSchema = z.object({
  route_id: z.string(),
  label: z.string(),
  fit: z.string(),
  rank: z.number(),
  methods: z.array(z.string()),
  rationale: z.string(),
  risks: z.array(z.string()),
  recommended_next_action: z.string().nullable().optional(),
  module_ids: z.array(z.string()),
  workflow_run_id: z.string().nullable().optional(),
  status: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
}).passthrough()

export const TargetExperimentPlanSchema = z.object({
  binding_validation: z.array(z.string()),
  specificity: z.array(z.string()),
  developability: z.array(z.string()),
  mutation_or_epitope_validation: z.array(z.string()),
}).passthrough()

export const TargetSourceStatusSchema = z.object({
  source_type: z.string(),
  status: z.enum(['ok', 'empty', 'failed', 'skipped']),
  item_count: z.number().optional(),
  detail: z.string().nullable().optional(),
}).passthrough()

export const TargetAgentStepSchema = z.object({
  role: z.string(),
  stage: z.string(),
  status: z.enum(['completed', 'skipped', 'failed']),
  summary: z.string(),
}).passthrough()

export const TargetAgentAuditSchema = z.object({
  agent_roles: z.array(z.string()),
  agent_steps: z.array(TargetAgentStepSchema).optional(),
  source_status: z.record(z.string(), TargetSourceStatusSchema).optional(),
  llm_provider: z.string().nullable().optional(),
  created_workflow_id: z.string().nullable().optional(),
  limitations: z.array(z.string()),
}).passthrough()

export const TargetIntelligenceStageSchema = z.enum([
  'collecting_evidence',
  'evidence_review',
  'mapping_hotspots',
  'hotspot_review',
  'planning_routes',
  'completed',
  'failed',
])

export type TargetIntelligenceStage = z.infer<typeof TargetIntelligenceStageSchema>

export const TargetIntelligenceReportSchema = z.object({
  run_id: z.string().nullable().optional(),
  stage: TargetIntelligenceStageSchema.default('collecting_evidence'),
  target: TargetIdentitySchema,
  evidence: z.array(TargetEvidenceItemSchema),
  hotspots: z.array(TargetHotspotSchema),
  design_routes: z.array(TargetDesignRouteSchema),
  experiment_plan: TargetExperimentPlanSchema,
  audit: TargetAgentAuditSchema,
}).passthrough()

export const TargetIntelligenceRunSchema = z.object({
  run_id: z.string(),
  project_id: z.string().nullable().optional(),
  target_query: z.string(),
  objective: z.string(),
  modality: z.string(),
  organism: z.string().nullable().optional(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  completed_at: z.string().nullable().optional(),
}).passthrough()

export const TargetRunDetailSchema = z.object({
  run: TargetIntelligenceRunSchema,
  report: TargetIntelligenceReportSchema,
})

export const ModuleSelectionOverrideSchema = z.object({
  used_modules: z.array(z.string()),
  requested_modules: z.array(z.string()),
  dropped_modules: z.array(z.string()),
  overridden: z.boolean(),
  reason: z.string(),
}).passthrough()

export const ParameterLineageEntrySchema = z.object({
  residue: z.string().nullable().optional(),
  region: z.string().nullable().optional(),
  evidence_level: z.string().nullable().optional(),
  extraction_method: z.string().nullable().optional(),
  source_refs: z.array(z.string()).optional(),
  parameter_targets: z.array(z.string()),
  rationale: z.string(),
}).passthrough()

export const TargetRouteApplyResultSchema = AppliedRoutePlanSchema.extend({
  target_route_id: z.string(),
  workflow_route_id: z.string(),
  status: z.string(),
  module_selection_note: z.string(),
  module_selection_override: ModuleSelectionOverrideSchema.optional(),
  parameter_lineage: z.array(ParameterLineageEntrySchema).optional(),
  next_actions: z.array(z.string()).optional(),
  safety: z.string(),
}).passthrough()

export const TargetDossierExportSchema = z.object({
  run_id: z.string(),
  export_format: z.string(),
  filename: z.string(),
  media_type: z.string(),
  content: z.string(),
})

export const ScoreSignalSchema = z.object({
  metric: z.string(),
  value: z.string(),
  assessment: z.enum(['favorable', 'neutral', 'unfavorable', 'unknown']),
  rationale: z.string(),
})

export const InterpretationReasoningSchema = z.object({
  subject_id: z.string(),
  subject_type: z.enum(['project', 'candidate']),
  headline: z.string(),
  signals: z.array(ScoreSignalSchema),
  decision: z.enum(['advance', 'hold', 'redesign', 'insufficient_data']),
  decision_rationale: z.string(),
  next_actions: z.array(z.string()),
  caveats: z.array(z.string()),
}).passthrough()

export type RoutePlan = z.infer<typeof RoutePlanSchema>
export type RouteOption = z.infer<typeof RouteOptionSchema>
export type RouteModule = z.infer<typeof RouteModuleSchema>
export type TargetIntelligenceReport = z.infer<typeof TargetIntelligenceReportSchema>
export type TargetDesignRoute = z.infer<typeof TargetDesignRouteSchema>
export type TargetRunDetail = z.infer<typeof TargetRunDetailSchema>
export type TargetDossierExport = z.infer<typeof TargetDossierExportSchema>
export type TargetEvidenceItem = z.infer<typeof TargetEvidenceItemSchema>
export type TargetHotspot = z.infer<typeof TargetHotspotSchema>
export type TargetSourceStatus = z.infer<typeof TargetSourceStatusSchema>
export type TargetAgentStep = z.infer<typeof TargetAgentStepSchema>
export type ModuleSelectionOverride = z.infer<typeof ModuleSelectionOverrideSchema>
export type ParameterLineageEntry = z.infer<typeof ParameterLineageEntrySchema>
export type InterpretationReasoning = z.infer<typeof InterpretationReasoningSchema>
export type ScoreSignal = z.infer<typeof ScoreSignalSchema>

export function planRoute(payload: {
  project_id: string
  target?: string
  objective: string
  constraints?: Record<string, unknown>
}) {
  return createRoutePlanApiV2CopilotRoutePlansPost<true>({
    body: { project_id: payload.project_id, goal: payload.objective }, throwOnError: true,
  }).then(({ data: plan }) => RoutePlanSchema.parse({
    mode: 'service',
    project_id: plan.project_id,
    target: payload.target ?? '',
    objective: plan.goal,
    constraints: payload.constraints ?? {},
    knowledge_context: plan.knowledge_context,
    analysis_trace: plan.rationale,
    route_options: plan.route_options,
  }))
}

export function applyRoutePlan(payload: {
  project_id: string
  route_id: string
  objective: string
  selected_module_ids: string[]
  /**
   * The planner's per-module defaults, keyed by module id. Without these the
   * created nodes would start empty and the route's recommended parameters —
   * the reason the plan is worth following — would be dropped on creation.
   */
  module_parameters?: Record<string, Record<string, unknown>>
  target?: string
  constraints?: Record<string, unknown>
}) {
  return listModelPluginsApiV2RegistryModelPluginsGet<true>({
    query: { limit: 200 },
    throwOnError: true,
  }).then(async ({ data: page }) => {
    const byId = new Map(page.items.map((plugin) => [plugin.id, plugin]))
    const plugins = payload.selected_module_ids.map((id) => byId.get(id)).filter((plugin) => plugin?.enabled)
    if (plugins.length !== payload.selected_module_ids.length) {
      throw new Error('One or more selected route modules are unavailable')
    }
    const nodes = plugins.map((plugin, index) => ({
      key: `${plugin!.plugin_key.toLowerCase()}-${index + 1}`,
      node_type: plugin!.plugin_key,
      model_plugin: plugin!.name,
      model_plugin_id: plugin!.id,
      container_image: plugin!.container_image,
      command: plugin!.command,
      parameters: payload.module_parameters?.[payload.selected_module_ids[index]] ?? {},
    }))
    const edges = nodes.slice(1).map((node, index) => ({
      source: nodes[index].key,
      target: node.key,
    }))
    const { data: workflow } = await postWorkflowApiV2ProjectsProjectIdWorkflowRunsPost<true>({
      path: { project_id: payload.project_id },
      body: { name: payload.objective, nodes, edges },
      throwOnError: true,
    })
    const { data: graph } = await getWorkflowGraphApiV2WorkflowRunsWorkflowIdGraphGet<true>({
      path: { workflow_id: workflow.id },
      throwOnError: true,
    })
    return AppliedRoutePlanSchema.parse({ workflow_run: workflow, nodes: graph.nodes,
      edges: graph.edges.map((edge, index) => ({ id: `route-edge-${index + 1}`, ...edge })),
      route: { route_id: payload.route_id, label: payload.route_id, rank: 1, recommended: true,
        summary: payload.objective, rationale: [], modules: payload.selected_module_ids.map((id, index) => ({
          module_id: id, model_plugin_id: id, model_name: plugins[index]!.name,
          node_type: plugins[index]!.plugin_key, available: true, summary: `${plugins[index]!.name} route step ${index + 1}`,
        })), risks: [], estimated_steps: nodes.length },
      knowledge_context: [], analysis_trace: ['Workflow created from a v2 Copilot route plan.'] })
  })
}

export function analyzeTargetIntelligence(payload: {
  project_id?: string
  target_query: string
  objective: string
  modality?: string
  organism?: string
  constraints?: Record<string, unknown>
}) {
  if (!payload.project_id) return Promise.reject(new Error('A project is required for target intelligence.'))
  return getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet<true>({ path: { project_id: payload.project_id },
    throwOnError: true }).then(({ data: target }) =>
    postRunApiV2ProjectsProjectIdIntelligenceRunsPost<true>({ path: { project_id: payload.project_id! },
      body: { target_id: target.id, query: payload }, throwOnError: true })).then(({ data: run }) =>
        TargetIntelligenceReportSchema.parse({ run_id: run.id, stage: 'collecting_evidence',
          target: { name: payload.target_query, organism: payload.organism, confidence: 'pending' },
          evidence: [], hotspots: [], design_routes: [], experiment_plan: { binding_validation: [], specificity: [],
            developability: [], mutation_or_epitope_validation: [] },
          audit: { agent_roles: ['intelligence'], limitations: ['Analysis is running asynchronously.'] } }))
}

export function getTargetIntelligenceRun(runId: string) {
  return getRunApiV2IntelligenceRunsRunIdGet<true>({ path: { run_id: runId }, throwOnError: true })
    .then(({ data: detail }) => {
    const run = detail.run
    const report = detail.report
    return TargetRunDetailSchema.parse({ run: { run_id: run.id, project_id: run.project_id,
      target_query: String(run.query?.target_query ?? ''), objective: String(run.query?.objective ?? ''),
      modality: String(run.query?.modality ?? 'auto'), status: run.status, created_at: run.created_at, updated_at: run.updated_at },
      report: { run_id: run.id, stage: run.status === 'succeeded' ? 'completed' : 'collecting_evidence',
        target: report?.content?.target ?? { name: String(run.query?.target_query ?? run.target_id), confidence: 'derived' },
        evidence: (detail.evidence ?? []).map((item) => ({ ...item, source_type: item.evidence_type,
          title: String(item.citation?.title ?? item.evidence_type), claim: item.content, claim_type: 'evidence',
          evidence_level: 'D', confidence: String(item.confidence ?? 'unknown') })),
        hotspots: (detail.hotspots ?? []).map((item) => ({ ...item, residue: item.label,
          region: 'unknown', evidence_level: 'D', confidence: 'unknown', status: item.review_status })),
        design_routes: (detail.routes ?? []).map((item, index: number) => ({ route_id: item.id,
          label: item.name, fit: 'derived', rank: index + 1, methods: [], rationale: item.name, risks: [],
          module_ids: [], workflow_run_id: item.applied_workflow_id, status: item.status })),
        experiment_plan: report?.content?.experiment_plan ?? { binding_validation: [], specificity: [],
          developability: [], mutation_or_epitope_validation: [] },
        audit: { agent_roles: ['intelligence'], limitations: report?.content?.limitations ?? [] } } })
  })
}

export function advanceTargetIntelligenceRun(runId: string) {
  return getTargetIntelligenceRun(runId).then((detail) => detail.report)
}

export function reviewTargetEvidence(
  runId: string,
  evidenceItemId: string,
  reviewStatus: 'accepted' | 'rejected' | 'pending_review',
) {
  return getEvidenceApiV2IntelligenceEvidenceEvidenceIdGet<true>({ path: { evidence_id: evidenceItemId },
    throwOnError: true }).then(({ data: current }) =>
    reviewEvidenceApiV2IntelligenceEvidenceEvidenceIdPatch<true>({ path: { evidence_id: evidenceItemId },
      headers: { 'If-Match': `W/"${current.version}"` },
      body: { review_status: reviewStatus === 'pending_review' ? 'pending' : reviewStatus }, throwOnError: true }),
  )
    .then(() => getTargetIntelligenceRun(runId)).then((detail) => detail.report)
}

export function reviewTargetHotspot(
  runId: string,
  hotspotId: string,
  payload: { status: 'confirmed' | 'rejected'; residue?: string; region?: string; note?: string },
) {
  return getHotspotApiV2IntelligenceHotspotsHotspotIdGet<true>({ path: { hotspot_id: hotspotId },
    throwOnError: true }).then(({ data: current }) =>
    reviewHotspotApiV2IntelligenceHotspotsHotspotIdPatch<true>({ path: { hotspot_id: hotspotId },
      headers: { 'If-Match': `W/"${current.version}"` },
      body: { review_status: payload.status === 'confirmed' ? 'accepted' : 'rejected', rationale: payload.note },
      throwOnError: true }),
  )
    .then(() => getTargetIntelligenceRun(runId)).then((detail) => detail.report)
}

export function applyTargetDesignRoute(_runId: string, payload: {
  project_id?: string
  route_id: string
  selected_module_ids?: string[]
  constraints?: Record<string, unknown>
}) {
  return postApplyRouteApiV2DesignRoutesRouteIdApplyPost<true>({ path: { route_id: payload.route_id },
    throwOnError: true }).then(({ data: workflow }) => TargetRouteApplyResultSchema.parse({ workflow_run: workflow,
    nodes: [], edges: [], route: { route_id: payload.route_id, label: payload.route_id, rank: 1, recommended: true,
      summary: 'Applied intelligence route', rationale: [], modules: [], risks: [], estimated_steps: 0 },
    knowledge_context: [], analysis_trace: [], target_route_id: payload.route_id, workflow_route_id: payload.route_id,
    status: 'applied', module_selection_note: '', safety: 'Human review required' }))
}

export function exportTargetDossier(runId: string, exportFormat: 'json' | 'markdown') {
  return postExportApiV2IntelligenceRunsRunIdExportsPost<true>({ path: { run_id: runId },
    throwOnError: true,
  }).then(({ data: operation }) => TargetDossierExportSchema.parse({ run_id: runId, export_format: exportFormat,
    filename: `intelligence-${runId}.${exportFormat === 'markdown' ? 'md' : 'json'}`,
    media_type: exportFormat === 'markdown' ? 'text/markdown' : 'application/json',
    content: JSON.stringify(operation, null, 2) }))
}

export function explainCandidate(candidateId: string) {
  return getCandidateApiV2CandidatesCandidateIdGet<true>({ path: { candidate_id: candidateId }, throwOnError: true })
    .then(({ data: candidate }) => createInterpretationApiV2CopilotInterpretationsPost<true>({ body: {
      project_id: candidate.project_id, subject: 'candidate', candidate_id: candidateId,
    }, throwOnError: true })).then(({ data: result }) => InterpretationReasoningSchema.parse({
        subject_id: candidateId, subject_type: 'candidate', headline: result.summary,
        signals: result.observations.map((item: string) => ({ metric: 'observation', value: item,
          assessment: 'neutral', rationale: item })), decision: 'insufficient_data', decision_rationale: result.summary,
        next_actions: [], caveats: result.limitations }))
}

export function interpretResults(projectId: string) {
  return createInterpretationApiV2CopilotInterpretationsPost<true>({ body: {
    project_id: projectId, subject: 'results',
  }, throwOnError: true }).then(({ data: result }) => InterpretationReasoningSchema.parse({ subject_id: projectId, subject_type: 'project',
    headline: result.summary, signals: result.observations.map((item: string) => ({ metric: 'observation', value: item,
      assessment: 'neutral', rationale: item })), decision: 'insufficient_data', decision_rationale: result.summary,
    next_actions: [], caveats: result.limitations }))
}
