import { API_BASE, apiAuthorizationHeaders } from './client'
import './generatedTransport'
import {
  getArtifactApiV2ArtifactsArtifactIdGet,
  listArtifactsApiV2ArtifactsGet,
  postCompleteApiV2ArtifactUploadsUploadIdCompletePost,
  postUploadApiV2ArtifactUploadsPost,
} from './generated/sdk.gen'
import type { ArtifactPage } from './generated/types.gen'
import { ArtifactSchema, type Artifact } from '../schemas/artifact'

function inferFormat(filename: string): string {
  const suffix = filename.toLowerCase().split('.').pop()
  if (suffix === 'cif') return 'mmcif'
  return suffix || 'file'
}

function inferArtifactType(format: string): string {
  if (['pdb', 'mmcif', 'cif'].includes(format)) return 'structure'
  if (['fasta', 'fa', 'faa'].includes(format)) return 'sequence'
  if (['csv', 'tsv', 'xlsx'].includes(format)) return 'score_table'
  if (format === 'json') return 'constraints'
  if (format === 'zip') return 'bundle'
  return 'file'
}

export async function uploadArtifact(file: File, projectId?: string): Promise<Artifact> {
  if (!projectId) throw new Error('A project is required for artifact uploads.')
  const format = inferFormat(file.name)
  const artifactType = inferArtifactType(format)
  const uploadResult = await postUploadApiV2ArtifactUploadsPost<true>({
    body: { project_id: projectId, filename: file.name,
      artifact_type: artifactType === 'structure' ? 'target_structure' : artifactType,
      content_type: file.type || 'application/octet-stream' },
    throwOnError: true,
  })
  const upload = uploadResult.data
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  const checksum = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  const response = await fetch(upload.upload_url, { method: 'PUT', headers: upload.required_headers, body: file })
  if (!response.ok) throw new Error(`Object upload failed (${response.status})`)
  const artifact = await postCompleteApiV2ArtifactUploadsUploadIdCompletePost<true>({
    path: { upload_id: upload.id },
    body: { checksum_sha256: checksum, lineage: { source: 'browser_upload' }, lineage_edges: [] },
    throwOnError: true,
  })
  return ArtifactSchema.parse(artifact.data)
}

export async function listProjectArtifacts(projectId: string): Promise<Artifact[]> {
  const items: Artifact[] = []
  let cursor: string | null = null
  do {
    const page: ArtifactPage = (await listArtifactsApiV2ArtifactsGet<true>({
      query: { project_id: projectId, cursor, limit: 200 },
      throwOnError: true,
    })).data
    items.push(...page.items.map((item) => ArtifactSchema.parse(item)))
    cursor = page.next_cursor ?? null
  } while (cursor)
  return items
}

export async function getArtifact(artifactId: string): Promise<Artifact> {
  const artifact = await getArtifactApiV2ArtifactsArtifactIdGet<true>({
    path: { artifact_id: artifactId },
    throwOnError: true,
  })
  return ArtifactSchema.parse(artifact.data)
}

export async function downloadArtifact(artifact: Artifact): Promise<void> {
  const url = artifact.download_url
  if (!url) throw new Error('No download URL is available for this artifact.')
  const baseOrigin = API_BASE.startsWith('http') ? new URL(API_BASE).origin : ''
  const downloadUrl = url.startsWith('http://') || url.startsWith('https://') ? url : url.startsWith('/api/')
    ? `${baseOrigin}${url}`
    : `${API_BASE}${url.startsWith('/') ? url : `/${url}`}`
  const response = await fetch(downloadUrl, {
    headers: apiAuthorizationHeaders(downloadUrl),
  })
  if (!response.ok) {
    throw new Error(`Artifact download failed (${response.status})`)
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = artifact.filename || artifact.id
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
