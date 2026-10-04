import './generatedTransport'
import {
  listChunksApiV2LiteratureDocumentsDocumentIdChunksGet,
  listDocumentRetrievalTracesApiV2LiteratureDocumentsDocumentIdRetrievalTracesGet,
} from './generated/sdk.gen'

export async function listSavedLiteratureChunks(documentId: string, cursor?: string) {
  return (await listChunksApiV2LiteratureDocumentsDocumentIdChunksGet<true>({
    path: { document_id: documentId }, query: { cursor, limit: 50 }, throwOnError: true,
  })).data
}

export async function listSavedLiteratureTraces(documentId: string, cursor?: string) {
  return (await listDocumentRetrievalTracesApiV2LiteratureDocumentsDocumentIdRetrievalTracesGet<true>({
    path: { document_id: documentId }, query: { cursor, limit: 50 }, throwOnError: true,
  })).data
}
