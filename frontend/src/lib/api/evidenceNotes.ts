import './generatedTransport'
import {
  createEvidenceNoteApiV2LiteratureDocumentsDocumentIdEvidenceNotesPost,
  listEvidenceNotesApiV2ProjectsProjectIdLiteratureEvidenceNotesGet,
  reviewEvidenceNoteApiV2LiteratureEvidenceNotesNoteIdReviewPatch,
  updateEvidenceNoteApiV2LiteratureEvidenceNotesNoteIdPut,
  postSearchApiV2ProjectsProjectIdLiteratureSearchesPost,
  getSearchApiV2LiteratureSearchesSearchRunIdGet,
} from './generated/sdk.gen'
import type { EvidenceNoteWrite } from './generated/types.gen'

export async function listEvidenceNotes(projectId: string, cursor?: string) {
  return (await listEvidenceNotesApiV2ProjectsProjectIdLiteratureEvidenceNotesGet<true>({
    path: { project_id: projectId }, query: { cursor, limit: 100 }, throwOnError: true,
  })).data
}

export async function saveEvidenceNote(documentId: string, body: EvidenceNoteWrite, existing?: { id: string; version: number }) {
  if (existing) return (await updateEvidenceNoteApiV2LiteratureEvidenceNotesNoteIdPut<true>({
    path: { note_id: existing.id }, headers: { 'If-Match': `W/"${existing.version}"` }, body, throwOnError: true,
  })).data
  return (await createEvidenceNoteApiV2LiteratureDocumentsDocumentIdEvidenceNotesPost<true>({
    path: { document_id: documentId }, body, throwOnError: true,
  })).data
}

export async function reviewEvidenceNote(id: string, version: number, reviewStatus: 'accepted' | 'rejected' | 'pending') {
  return (await reviewEvidenceNoteApiV2LiteratureEvidenceNotesNoteIdReviewPatch<true>({
    path: { note_id: id }, headers: { 'If-Match': `W/"${version}"` }, body: { review_status: reviewStatus }, throwOnError: true,
  })).data
}

export async function retrieveEvidenceSource(projectId: string, query: string) {
  return (await postSearchApiV2ProjectsProjectIdLiteratureSearchesPost<true>({
    path: { project_id: projectId }, body: { query, sources: ['europe_pmc'], limit: 1, fetch_full_text: true, extract_claims: false }, throwOnError: true,
  })).data
}

export async function getEvidenceSourceRetrieval(id: string) {
  return (await getSearchApiV2LiteratureSearchesSearchRunIdGet<true>({ path: { search_run_id: id }, throwOnError: true })).data
}
