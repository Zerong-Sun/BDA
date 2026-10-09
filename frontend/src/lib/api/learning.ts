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
  withdrawLearningObservationApiV2ProjectsProjectIdLearningObservationsRecordIdWithdrawPost as withdrawObservationSdk,
  importLearningObservationsApiV2ProjectsProjectIdLearningObservationsImportPost as importSdk,
  postLearningEvidenceApiV2ProjectsProjectIdLearningEvidencePost as evidenceSdk,
  withdrawLearningEvidenceApiV2ProjectsProjectIdLearningEvidenceRecordIdWithdrawPost as withdrawSdk,
  postLearningBatchApiV2ProjectsProjectIdLearningBatchesPost as batchSdk,
  receiveLearningBatchApiV2ProjectsProjectIdLearningBatchesRecordIdReceivePost as receiveSdk,
  exportLearningDeliveryApiV2ProjectsProjectIdLearningStudiesRecordIdDeliveryGet as deliverySdk,
  getLearningRecordApiV2ProjectsProjectIdLearningKindRecordIdGet as recordSdk,
} from './generated/sdk.gen'
import type { AssayCreate, AssayResponse, StudyCreate, StudyResponse, DatasetResponse, ModelResponse,
  LearningDecisionCreate, LearningDecisionResponse, ObservationCreate, ModelCreate, ModelReview,
  BackendV2AppLearningSchemasEvidenceResponse as EvidenceResponse, EvidenceCreate, BatchResponse, BatchComplete, ObservationImport, ExperimentResultResponse } from './generated/types.gen'

export type { AssayResponse, StudyResponse, DatasetResponse, ModelResponse, LearningDecisionResponse, EvidenceResponse, BatchResponse }
type Records = { assays: AssayResponse; studies: StudyResponse; datasets: DatasetResponse; models: ModelResponse; decisions: LearningDecisionResponse; evidence: EvidenceResponse; batches: BatchResponse }

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
export async function trainLearningModel(projectId: string, datasetId: string, options: Omit<ModelCreate, 'dataset_id'> = {}) {
  return (await modelSdk<true>({ path: { project_id: projectId }, body: { dataset_id: datasetId, ...options }, throwOnError: true })).data
}
export async function reviewLearningModel(projectId: string, model: ModelResponse, action: ModelReview['action'], rationale: string) {
  return (await modelReviewSdk<true>({ path: { project_id: projectId, model_id: model.id }, headers: { 'If-Match': `W/"${model.version}"` }, body: { action, rationale }, throwOnError: true })).data
}
export async function createLearningDecision(projectId: string, body: LearningDecisionCreate) {
  return (await decisionSdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function reviewLearningDecision(projectId: string, decision: LearningDecisionResponse, approve: boolean, rationale: string) {
  return (await decisionReviewSdk<true>({ path: { project_id: projectId, decision_id: decision.id }, headers: { 'If-Match': `W/"${decision.version}"` }, body: { approve, rationale }, throwOnError: true })).data
}
export async function exportLearningDecision(projectId: string, decisionId: string) {
  return preserveExportText((await exportDecisionSdk<true>({ path: { project_id: projectId, decision_id: decisionId }, parseAs: 'text', throwOnError: true })).data)
}

/** JSON.parse/stringify changes 10.0 to 10, invalidating the server's hashed numeric representation. */
function preserveExportText(data: unknown): string {
  if (typeof data !== 'string') throw new Error('Export transport must preserve the original JSON text.')
  return data
}

export async function importObservations(projectId: string, body: ObservationImport) {
  return (await importSdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function createEvidence(projectId: string, body: EvidenceCreate) {
  return (await evidenceSdk<true>({ path: { project_id: projectId }, body, throwOnError: true })).data
}
export async function withdrawEvidence(projectId: string, record: EvidenceResponse, rationale: string) {
  return (await withdrawSdk<true>({ path: { project_id: projectId, record_id: record.id }, headers: { 'If-Match': `W/"${record.version}"` }, body: { rationale }, throwOnError: true })).data
}
export async function createLearningBatch(projectId: string, decision: LearningDecisionResponse, rationale: string, workflowRunId?: string) {
  return (await batchSdk<true>({ path: { project_id: projectId }, headers: { 'If-Match': `W/"${decision.version}"` }, body: { decision_id: decision.id, rationale, workflow_run_id: workflowRunId }, throwOnError: true })).data
}
export async function receiveLearningBatch(projectId: string, record: BatchResponse, body: BatchComplete) {
  return (await receiveSdk<true>({ path: { project_id: projectId, record_id: record.id }, headers: { 'If-Match': `W/"${record.version}"` }, body, throwOnError: true })).data
}
export async function exportLearningDelivery(projectId: string, studyId: string) {
  return preserveExportText((await deliverySdk<true>({ path: { project_id: projectId, record_id: studyId }, parseAs: 'text', throwOnError: true })).data)
}

export async function exportLearningBatch(projectId: string, batchId: string) {
  return preserveExportText((await recordSdk<true>({ path: { project_id: projectId, kind: 'batches', record_id: batchId }, parseAs: 'text', throwOnError: true })).data)
}

export async function withdrawObservation(projectId: string, record: ExperimentResultResponse, rationale: string) {
  return (await withdrawObservationSdk<true>({ path: { project_id: projectId, record_id: record.id }, headers: { 'If-Match': `W/"${record.version}"` }, body: { rationale }, throwOnError: true })).data
}
