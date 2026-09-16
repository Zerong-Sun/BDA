import './generatedTransport'
import {
  getPatentLandscapeApiV2ProjectsProjectIdPatentsLandscapeGet,
  postPatentClaimsLookupApiV2ProjectsProjectIdPatentsClaimsLookupsPost,
  postPatentLegalStatusLookupApiV2ProjectsProjectIdPatentsLegalStatusLookupsPost,
  searchPatentClaimsApiV2ProjectsProjectIdPatentsClaimsGet,
} from './generated/sdk.gen'
import { PatentClaimsPageSchema, PatentLandscapeSchema } from '../schemas/patents'

export async function getPatentLandscape(projectId: string) {
  return PatentLandscapeSchema.parse((await getPatentLandscapeApiV2ProjectsProjectIdPatentsLandscapeGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  })).data)
}
export async function queuePatentLookup(projectId: string, documentId: string, kind: 'claims' | 'legal') {
  const request = kind === 'claims' ? postPatentClaimsLookupApiV2ProjectsProjectIdPatentsClaimsLookupsPost
    : postPatentLegalStatusLookupApiV2ProjectsProjectIdPatentsLegalStatusLookupsPost
  return (await request<true>({ path: { project_id: projectId }, body: { document_ids: [documentId] }, throwOnError: true })).data
}
export async function searchPatentClaims(projectId: string, query: string, cursor?: string) {
  return PatentClaimsPageSchema.parse((await searchPatentClaimsApiV2ProjectsProjectIdPatentsClaimsGet<true>({
    path: { project_id: projectId }, query: { query, cursor }, throwOnError: true,
  })).data)
}
