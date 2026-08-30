import { ApiError } from './client'
import './generatedTransport'
import {
  candidateFunnelApiV2ProjectsProjectIdCandidateFunnelGet,
  deleteProjectApiV2ProjectsProjectIdDelete,
  getArtifactApiV2ArtifactsArtifactIdGet,
  getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet,
  getResultSummaryApiV2ProjectsProjectIdResultSummaryGet,
  getStructureRevisionApiV2TargetStructureRevisionsRevisionIdGet,
  getTargetStructureApiV2TargetsTargetIdStructureGet,
  listDeliveryApiV2ProjectsProjectIdDeliveryPackagesGet,
  listOrganizationsApiV2OrganizationsGet,
  listProjectsApiV2ProjectsGet,
  projectLibraryApiV2ProjectsLibraryGet,
  listWorkflowsApiV2ProjectsProjectIdWorkflowRunsGet,
  getProjectPromptDraftApiV2ProjectsPromptDraftsDraftIdGet,
  patchProjectApiV2ProjectsProjectIdPatch,
  patchTargetApiV2TargetsTargetIdPatch,
  postFindingApiV2ProjectsProjectIdResearchFindingsPost,
  postProjectApiV2ProjectsPost,
  postProjectPromptDraftApiV2ProjectsPromptDraftsPost,
  postTargetApiV2ProjectsProjectIdTargetsPost,
  prepareStructureApiV2TargetsTargetIdStructureRevisionsPost,
  projectOverviewApiV2ProjectsProjectIdOverviewGet,
  projectResearchSummaryApiV2ProjectsProjectIdResearchSummaryGet,
  putPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetPut,
  reviewStructureApiV2TargetStructureRevisionsRevisionIdReviewPost,
  targetReadinessApiV2ProjectsProjectIdTargetReadinessGet,
} from './generated/sdk.gen'
import type { ProjectLibraryPage, ProjectPage } from './generated/types.gen'
import {
  CandidateFunnelSchema,
  DeliveryPackageSchema,
  ResultsSummarySchema,
  type CandidateFunnel,
  type DeliveryPackageData,
  type ResultsSummary,
} from '../schemas/delivery'
import {
  ProjectLibraryItemSchema,
  ProjectOverviewSchema,
  ProjectSchema,
  type Project,
  type ProjectLibraryItem,
  type ProjectOverview,
} from '../schemas/project'
import {
  ProjectTargetStructureSchema,
  TargetReadinessSchema,
  type ProjectTargetStructure,
  type TargetReadiness,
  type TargetStructureRevision,
} from '../schemas/target'
import { ProjectResearchSummarySchema, type ProjectResearchSummary } from '../schemas/research'
import { isTerminalWorkflowRun, WorkflowRunSchema, type WorkflowRun } from '../schemas/workflow'
import { ArtifactSchema } from '../schemas/artifact'

export async function listProjects(): Promise<Project[]> {
  const projects: Project[] = []
  let cursor: string | null = null
  do {
    const page: ProjectPage = (await listProjectsApiV2ProjectsGet<true>({
      query: { cursor, limit: 200 }, throwOnError: true,
    })).data
    projects.push(...page.items.map((item) => ProjectSchema.parse(item)))
    cursor = page.next_cursor ?? null
  } while (cursor)
  return projects
}

export async function listProjectLibrary(): Promise<ProjectLibraryItem[]> {
  const items: ProjectLibraryItem[] = []
  let cursor: string | null = null
  do {
    const page: ProjectLibraryPage = (await projectLibraryApiV2ProjectsLibraryGet<true>({
      query: { cursor, limit: 200 },
      throwOnError: true,
    })).data
    items.push(...page.items.map((item) => ProjectLibraryItemSchema.parse(item)))
    cursor = page.next_cursor ?? null
  } while (cursor)
  return items
}

export interface CreateProjectPayload {
  name: string
  project_type: string
  summary?: string
  prompt: string
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  const organizations = (await listOrganizationsApiV2OrganizationsGet<true>({ throwOnError: true })).data
  if (!organizations[0]) throw new ApiError('No organization membership is available', 409)
  const project = await postProjectApiV2ProjectsPost<true>({
    body: { organization_id: organizations[0].id, name: payload.name,
      project_type: payload.project_type, summary: payload.summary, prompt: payload.prompt },
    throwOnError: true,
  })
  return ProjectSchema.parse(project.data)
}

export interface CreateProjectPromptDraftPayload {
  name: string
  project_type: string
  summary?: string
}

export interface ProjectPromptDraft {
  id: string
  status: string
  prompt: string | null
  error: string | null
}

export async function createProjectPromptDraft(payload: CreateProjectPromptDraftPayload): Promise<{ draft_id: string }> {
  const organizations = (await listOrganizationsApiV2OrganizationsGet<true>({ throwOnError: true })).data
  if (!organizations[0]) throw new ApiError('No organization membership is available', 409)
  const accepted = await postProjectPromptDraftApiV2ProjectsPromptDraftsPost<true>({
    body: { organization_id: organizations[0].id, name: payload.name,
      project_type: payload.project_type, summary: payload.summary },
    throwOnError: true,
  })
  return accepted.data
}

export function getProjectPromptDraft(draftId: string): Promise<ProjectPromptDraft> {
  return getProjectPromptDraftApiV2ProjectsPromptDraftsDraftIdGet<true>({
    path: { draft_id: draftId }, throwOnError: true,
  }).then(({ data }) => data)
}

export async function waitForProjectPromptDraft(draftId: string): Promise<ProjectPromptDraft> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const draft = await getProjectPromptDraft(draftId)
    if (draft.status !== 'pending') return draft
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
  }
  throw new ApiError('Prompt generation did not finish within two minutes.', 408)
}

export async function updateProjectPrompt(projectId: string, prompt: string, expectedVersion: number): Promise<Project> {
  const updated = await patchProjectApiV2ProjectsProjectIdPatch<true>({
    path: { project_id: projectId },
    headers: { 'If-Match': `W/"${expectedVersion}"` },
    body: { prompt },
    throwOnError: true,
  })
  return ProjectSchema.parse(updated.data)
}

export interface DeleteProjectResult {
  id: string
  deleted: boolean
  retention_days?: number
}

export interface ResearchFindingUpsertPayload {
  finding_type: string
  title: string
  content: string
  brief_id?: string | null
  evidence?: Record<string, unknown>
}

export function deleteProject(projectId: string): Promise<DeleteProjectResult> {
  return deleteProjectApiV2ProjectsProjectIdDelete<true>({
    path: { project_id: projectId }, throwOnError: true,
  }).then((response) => response.data)
}

export async function getProjectOverview(projectId: string) {
  const overview = await projectOverviewApiV2ProjectsProjectIdOverviewGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  })
  return ProjectOverviewSchema.parse(overview.data)
}

export function getProjectTargetStructure(projectId: string) {
  return getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet<true>({ path: { project_id: projectId },
    throwOnError: true }).then(async ({ data: target }) => {
    const structure = (await getTargetStructureApiV2TargetsTargetIdStructureGet<true>({ path: { target_id: target.id },
      throwOnError: true })).data
    const artifactId = typeof structure.current_artifact_id === 'string' ? structure.current_artifact_id : null
    const artifact = artifactId
      ? ArtifactSchema.parse((await getArtifactApiV2ArtifactsArtifactIdGet<true>({ path: { artifact_id: artifactId },
        throwOnError: true })).data)
      : null
    return ProjectTargetStructureSchema.parse({ target, structure, artifact })
  })
}

export async function getProjectTargetStructureOrNull(projectId: string): Promise<ProjectTargetStructure | null> {
  try {
    return await getProjectTargetStructure(projectId)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export function getTargetReadiness(projectId: string) {
  return targetReadinessApiV2ProjectsProjectIdTargetReadinessGet<true>({ path: { project_id: projectId },
    throwOnError: true }).then(({ data }) => TargetReadinessSchema.parse(data))
}

export interface ConfirmTargetIdentityPayload {
  target_name: string
  uniprot_accession?: string
  organism?: string
  construct_start?: number
  construct_end?: number
  /** A de novo or synthetic target has no accession; the sequence is its identity. */
  sequence?: string
  /** 'small_molecule' targets are identified by a chemical identifier and never carry
   *  uploaded coordinates - the model resolves them from its own component library. */
  target_kind?: 'protein' | 'small_molecule'
  /** Any one of ccd / inchikey / smiles identifies the molecule. */
  chemical_identity?: Record<string, unknown>
}

export function confirmTargetIdentity(projectId: string, payload: ConfirmTargetIdentityPayload) {
  return getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet<true>({ path: { project_id: projectId },
    throwOnError: true }).then(({ data }) => data).catch((error) => {
    if (!(error instanceof ApiError) || error.status !== 404) throw error
    return postTargetApiV2ProjectsProjectIdTargetsPost<true>({ path: { project_id: projectId }, body: {
      name: payload.target_name, uniprot_accession: payload.uniprot_accession, organism: payload.organism,
      sequence: payload.sequence, target_kind: payload.target_kind,
      chemical_identity: payload.chemical_identity,
    }, throwOnError: true }).then(async ({ data: target }) => {
      await putPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetPut<true>({ path: { project_id: projectId },
        body: { target_id: target.id }, throwOnError: true })
      return target
    })
  }).then(async (target) => {
    const updated = (await patchTargetApiV2TargetsTargetIdPatch<true>({ path: { target_id: target.id },
      headers: { 'If-Match': `W/"${target.version}"` }, body: { name: payload.target_name,
        uniprot_accession: payload.uniprot_accession, organism: payload.organism,
        // Forwarded so a target whose identity is a sequence or a chemical identifier can
        // actually reach identity_status='confirmed'. Sending only the accession meant a
        // ligand-only project could never satisfy target readiness, which is what left
        // the Workflow page permanently read-only.
        sequence: payload.sequence, target_kind: payload.target_kind,
        chemical_identity: payload.chemical_identity }, throwOnError: true })).data
    const readiness = await getTargetReadiness(projectId)
    return { target: updated, readiness }
  })
}

export function prepareTargetStructure(
  projectId: string,
  payload: { selected_chains: string[]; remove_waters: boolean; remove_heteroatoms: boolean },
) {
  return getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet<true>({ path: { project_id: projectId },
    throwOnError: true }).then(async ({ data: target }) => {
    if (!target.structure_artifact_id) throw new ApiError('Target structure artifact is required', 409)
    const revision = (await prepareStructureApiV2TargetsTargetIdStructureRevisionsPost<true>({ path: { target_id: target.id },
      body: { source_artifact_id: target.structure_artifact_id, ...payload }, throwOnError: true })).data
    return { revision, readiness: await getTargetReadiness(projectId) }
  })
}

export function approveTargetStructure(projectId: string, revisionId: string, approve = true) {
  return getStructureRevisionApiV2TargetStructureRevisionsRevisionIdGet<true>({ path: { revision_id: revisionId },
    throwOnError: true }).then(({ data: current }) =>
    reviewStructureApiV2TargetStructureRevisionsRevisionIdReviewPost<true>({ path: { revision_id: revisionId },
      headers: { 'If-Match': `W/"${current.version}"` }, body: { approve }, throwOnError: true }),
  ).then(async ({ data: revision }) => ({ revision, readiness: await getTargetReadiness(projectId) }))
}

export function getCandidateFunnel(projectId: string) {
  return candidateFunnelApiV2ProjectsProjectIdCandidateFunnelGet<true>({ path: { project_id: projectId },
    throwOnError: true }).then(({ data }) => CandidateFunnelSchema.parse(data))
}

export async function getResultsSummary(projectId: string) {
  const summary = await getResultSummaryApiV2ProjectsProjectIdResultSummaryGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  })
  return ResultsSummarySchema.parse(summary.data)
}

export async function getDeliveryPackage(projectId: string) {
  const page = (await listDeliveryApiV2ProjectsProjectIdDeliveryPackagesGet<true>({
    path: { project_id: projectId }, query: { limit: 1 }, throwOnError: true,
  })).data
  if (!page.items[0]) throw new ApiError('Delivery package was not found', 404)
  return DeliveryPackageSchema.parse(page.items[0])
}

export async function getDeliveryPackageOrNull(projectId: string): Promise<DeliveryPackageData | null> {
  try {
    return await getDeliveryPackage(projectId)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export function getLatestWorkflowRun(projectId: string) {
  return listProjectWorkflowRuns(projectId).then((runs) => {
    if (!runs[0]) throw new ApiError('Workflow run was not found', 404)
    return runs[0]
  })
}

/** A run the canvas can actually draw. `New workflow` starts out with an empty graph. */
export function hasWorkflowNodes(run: WorkflowRun): boolean {
  const nodes = (run.graph as { nodes?: unknown }).nodes
  return Array.isArray(nodes) && nodes.length > 0
}

/**
 * Runs replaced by a later one, hidden from the route switcher.
 *
 * A route is a run here, so a superseded run is a duplicate way to open the same route -
 * and the stalest copy is often the one whose name a user searches for. Archived rather
 * than deleted: the row keeps its history and clearing `graph.archived` brings it back.
 */
export function isArchivedWorkflowRun(run: WorkflowRun): boolean {
  return Boolean((run.graph as { archived?: unknown }).archived)
}

export function getCurrentWorkflowRun(projectId: string) {
  return listProjectWorkflowRuns(projectId).then((runs) => {
    const active = runs.filter((run) => !isTerminalWorkflowRun(run.status))
    const drawable = active.filter(hasWorkflowNodes)
    // Recency alone is the wrong default twice over, and manuka hit both: two stray empty
    // `New workflow` drafts blanked the canvas, and registering a new planned route (Route
    // 0) would then have hidden the run that carries the actual results. So: prefer a run
    // that has both nodes and a status past `draft`, i.e. one that has actually started.
    const current =
      drawable.find((run) => run.status !== 'draft') ?? drawable[0] ?? active[0] ?? runs[0]
    if (!current) throw new ApiError('Workflow run was not found', 404)
    return current
  })
}

export function sortWorkflowRunsNewestFirst(runs: WorkflowRun[]): WorkflowRun[] {
  return [...runs].sort((left, right) => {
    const timeDifference = Date.parse(right.created_at) - Date.parse(left.created_at)
    return timeDifference || right.id.localeCompare(left.id)
  })
}

export function listProjectWorkflowRuns(projectId: string) {
  return listWorkflowsApiV2ProjectsProjectIdWorkflowRunsGet<true>({ path: { project_id: projectId },
    query: { limit: 200 }, throwOnError: true,
  }).then(({ data }) =>
    sortWorkflowRunsNewestFirst(
      // Archived runs are excluded here rather than at each call site, so the switcher,
      // the default selection and any future consumer agree on what a project's routes
      // are.
      data.items.map((item) => WorkflowRunSchema.parse(item)).filter((run) => !isArchivedWorkflowRun(run)),
    ))
}

export function getProjectResearchSummary(projectId: string) {
  return projectResearchSummaryApiV2ProjectsProjectIdResearchSummaryGet<true>({ path: { project_id: projectId },
    throwOnError: true }).then(({ data }) => ProjectResearchSummarySchema.parse(data))
}

export function upsertProjectResearchFinding(projectId: string, payload: ResearchFindingUpsertPayload) {
  return postFindingApiV2ProjectsProjectIdResearchFindingsPost<true>({ path: { project_id: projectId },
    body: payload, throwOnError: true,
  }).then(({ data }) => data)
}

export async function getLatestWorkflowRunOrNull(projectId: string): Promise<WorkflowRun | null> {
  try {
    return await getLatestWorkflowRun(projectId)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export async function getCurrentWorkflowRunOrNull(projectId: string): Promise<WorkflowRun | null> {
  try {
    return await getCurrentWorkflowRun(projectId)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export type { CandidateFunnel, DeliveryPackageData, ResultsSummary, Project, ProjectOverview, ProjectResearchSummary, ProjectTargetStructure, TargetReadiness, TargetStructureRevision }
