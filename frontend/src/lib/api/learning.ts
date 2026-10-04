import './generatedTransport'
import {
  exportLearningDecisionApiV2ProjectsProjectIdLearningDecisionsDecisionIdExportGet as exportDecisionSdk,
  listLearningRecordsApiV2ProjectsProjectIdLearningKindGet as listSdk,
  listResultsApiV2ProjectsProjectIdExperimentResultsGet as resultsSdk,
  postLearningAssayApiV2ProjectsProjectIdLearningAssaysPost as assaySdk,
  postLearningStudyApiV2ProjectsProjectIdLearningStudiesPost as studySdk,
  postLearningObservationApiV2ProjectsProjectIdLearningObservationsPost as observationSdk,
  postLearningDatasetApiV2ProjectsProjectIdLearningDatasetsPost as datasetSdk,
  postLearningModelApiV2ProjectsProjectIdLearningModelsPost as modelSdk,
  postLearningDecisionApiV2ProjectsProjectIdLearningDecisionsPost as decisionSdk,
  reviewLearningModelApiV2ProjectsProjectIdLearningModelsModelIdReviewPost as modelReviewSdk,
  reviewLearningDecisionApiV2ProjectsProjectIdLearningDecisionsDecisionIdReviewPost as decisionReviewSdk,
} from './generated/sdk.gen'
import type { AssayCreate, AssayResponse, StudyCreate, StudyResponse, DatasetResponse, ModelResponse,
  LearningDecisionCreate, LearningDecisionResponse, ObservationCreate } from './generated/types.gen'

export type { AssayResponse, StudyResponse, DatasetResponse, ModelResponse, LearningDecisionResponse }
type Records = { assays: AssayResponse; studies: StudyResponse; datasets: DatasetResponse; models: ModelResponse; decisions: LearningDecisionResponse }

/** Refuse an incomplete collection rather than silently optimizing a truncated pool. */
export async function collectLearningPages<T>(read: (cursor?: string) => Promise<{ items: T[]; next_cursor?: string | null }>): Promise<T[]> {
  const rows: T[] = []
  const seen = new Set<string>()
  let cursor: string | undefined
  for (let page = 0; page < 50; page += 1) {
    const response = await read(cursor)
    rows.push(...response.items)
    if (!response.next_cursor) return rows
    if (seen.has(response.next_cursor)) throw new Error('Pagination repeated a cursor; reload before continuing.')
    seen.add(response.next_cursor)
    cursor = response.next_cursor
  }
  throw new Error('This collection exceeds the interactive workbench limit. Narrow the project before continuing.')
}

export function listLearning<K extends keyof Records>(projectId: string, kind: K): Promise<Records[K][]> {
  return collectLearningPages(async (cursor) => {
    const { data } = await listSdk<true>({ path: { project_id: projectId, kind }, query: { cursor, limit: 50 }, throwOnError: true })
    // The backend selects its response schema from the same closed kind enum.
    return { ...data, items: data.items as Records[K][] }
  })
}
export function listLearningResults(projectId: string) {
  return collectLearningPages(async (cursor) => (await resultsSdk<true>({ path: { project_id: projectId }, query: { cursor, limit: 200 }, throwOnError: true })).data)
}
export async function createAssay(projectId: string, body: AssayCreate) {
  return (await assaySdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function createStudy(projectId: string, body: StudyCreate) {
  return (await studySdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function createObservation(projectId: string, body: ObservationCreate) {
  return (await observationSdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function freezeDataset(projectId: string, studyId: string, resultIds: string[]) {
  return (await datasetSdk<true>({ path: { project_id: projectId }, body: { study_id: studyId, result_ids: resultIds }, throwOnError: true })).data
}
export async function trainLearningModel(projectId: string, datasetId: string) {
  return (await modelSdk<true>({ path: { project_id: projectId }, body: { dataset_id: datasetId }, throwOnError: true })).data
}
export async function reviewLearningModel(projectId: string, model: ModelResponse, action: 'promote' | 'retire', rationale: string) {
  return (await modelReviewSdk<true>({ path: { project_id: projectId, model_id: model.id }, headers: { 'If-Match': `W/"${model.version}"` }, body: { action, rationale }, throwOnError: true })).data
}
export async function createLearningDecision(projectId: string, body: LearningDecisionCreate) {
  return (await decisionSdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function reviewLearningDecision(projectId: string, decision: LearningDecisionResponse, approve: boolean, rationale: string) {
  return (await decisionReviewSdk<true>({ path: { project_id: projectId, decision_id: decision.id }, headers: { 'If-Match': `W/"${decision.version}"` }, body: { approve, rationale }, throwOnError: true })).data
}
export async function exportLearningDecision(projectId: string, decisionId: string) {
  return (await exportDecisionSdk<true>({ path: { project_id: projectId, decision_id: decisionId }, throwOnError: true })).data
}
