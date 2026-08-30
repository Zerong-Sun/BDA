import './generatedTransport'
import { ApiError } from './client'
import { uploadArtifact } from './artifacts'
import {
  attachStructureArtifactApiV2TargetsTargetIdStructureArtifactPut,
  getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet,
  importTargetStructureApiV2TargetsTargetIdStructureImportsPost,
  postTargetApiV2ProjectsProjectIdTargetsPost,
  postLigandImportApiV2ProjectsProjectIdLigandImportsPost,
  putPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetPut,
} from './generated/sdk.gen'
import type {
  ArtifactResponse,
  LigandImportAccepted,
  TargetResponse,
  TargetStructureImportAccepted,
} from './generated/types.gen'

export interface StructureUploadResult {
  artifact: ArtifactResponse
  target: TargetResponse
}

export async function uploadPdb(file: File, projectId?: string): Promise<StructureUploadResult> {
  if (!projectId) throw new Error('A project is required for structure uploads.')
  const artifact = await uploadArtifact(file, projectId)
  const current = await getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  }).catch(async (error) => {
    if (!(error instanceof ApiError) || error.status !== 404) throw error
    const created = await postTargetApiV2ProjectsProjectIdTargetsPost<true>({
      path: { project_id: projectId },
      body: { name: file.name.replace(/\.(?:pdb|cif|mmcif)$/i, '') },
      throwOnError: true,
    })
    await putPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetPut<true>({
      path: { project_id: projectId },
      body: { target_id: created.data.id },
      throwOnError: true,
    })
    return created
  })
  const attached = await attachStructureArtifactApiV2TargetsTargetIdStructureArtifactPut<true>({
    path: { target_id: current.data.id },
    body: { artifact_id: artifact.id },
    headers: { 'If-Match': `W/"${current.data.version}"` },
    throwOnError: true,
  })
  return { artifact, target: attached.data }
}

export async function fetchPdb(
  pdbId: string,
  projectId: string,
  format: 'cif' | 'pdb' = 'pdb',
): Promise<TargetStructureImportAccepted> {
  const target = await getPrimaryTargetApiV2ProjectsProjectIdPrimaryTargetGet<true>({
    path: { project_id: projectId }, throwOnError: true,
  })
  const response = await importTargetStructureApiV2TargetsTargetIdStructureImportsPost<true>({
    path: { target_id: target.data.id },
    body: { source: 'pdb', pdb_id: pdbId, format },
    throwOnError: true,
  })
  return response.data
}

export interface LigandPreset {
  key: string
  label: string
  pubchem_name: string
  cid: number
}

export const CANNABINOID_LIGANDS: LigandPreset[] = [
  { key: 'thc', label: 'THC', pubchem_name: 'delta-9-tetrahydrocannabinol', cid: 16078 },
  { key: 'cbd', label: 'CBD', pubchem_name: 'cannabidiol', cid: 644019 },
  { key: 'cbn', label: 'CBN', pubchem_name: 'cannabinol', cid: 2543 },
  { key: 'cbg', label: 'CBG', pubchem_name: 'cannabigerol', cid: 5315659 },
  { key: 'thc-cooh', label: 'THC-COOH', pubchem_name: '11-nor-9-carboxy-delta-9-tetrahydrocannabinol', cid: 107885 },
  { key: '11-oh-thc', label: '11-OH-THC', pubchem_name: '11-hydroxy-delta-9-tetrahydrocannabinol', cid: 644094 },
]

export function fetchLigand(name: string, projectId: string, source: string): Promise<LigandImportAccepted> {
  return postLigandImportApiV2ProjectsProjectIdLigandImportsPost<true>({
    path: { project_id: projectId },
    body: { ligand_id: name, source },
    throwOnError: true,
  }).then((response) => response.data)
}
