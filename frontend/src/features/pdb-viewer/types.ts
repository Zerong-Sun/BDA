import { resolveApiUrl } from '../../lib/api/client'
import { candidateScore, candidateStrings, type Candidate } from '../../lib/schemas/candidate'
import type { ProjectTargetStructure } from '../../lib/schemas/target'

export type StructureFormat = 'pdb' | 'mmcif' | 'alphafold'

export interface HighlightedResidue {
  chainId: string
  seq: number
  label?: string
}

export interface StructureLigand {
  id: string
  name?: string
}

export interface StructureSource {
  projectId?: string
  candidateId?: string
  artifactId?: string
  url?: string | null
  file?: File | null
  format?: StructureFormat
  proteinName?: string
  pdbId?: string | null
  alphafoldId?: string | null
  chains?: string[]
  atomCount?: number | null
  ligands?: StructureLigand[]
  highlightedResidues?: HighlightedResidue[]
  confidenceScore?: number | null
  designScore?: number | null
}

export interface StructureMetadataResponse {
  chains: string[]
  atom_count: number
  chain_count: number
  residue_count: number
  ligands: StructureLigand[]
  format?: StructureFormat
}

export function hasStructureData(source: StructureSource | null | undefined): boolean {
  return Boolean(source?.url || source?.file)
}

export function structureSourceFromTarget(
  target: ProjectTargetStructure,
  projectId?: string,
  overrides: Partial<StructureSource> = {},
): StructureSource {
  const url = resolveApiUrl(target.artifact?.download_url)
  const format = inferFormatFromPath(target.artifact?.filename)
  const lineageChains = target.artifact?.lineage.chains
  const chains = Array.isArray(lineageChains)
    ? lineageChains.filter((item): item is string => typeof item === 'string')
    : undefined
  const atomCount = target.artifact?.lineage.atom_count
  return {
    projectId,
    artifactId: target.artifact?.id,
    url,
    format,
    proteinName: target.target.name,
    pdbId: typeof target.artifact?.lineage.pdb_id === 'string' ? target.artifact.lineage.pdb_id : null,
    chains,
    atomCount: typeof atomCount === 'number' ? atomCount : null,
    confidenceScore: null,
    designScore: null,
    ...overrides,
  }
}

export function structureSourceFromCandidate(
  candidate: Candidate,
  options: {
    structureMode?: 'monomer' | 'complex'
    downloadUrl?: string | null
    metadata?: StructureMetadataResponse | null
    highlightedResidues?: HighlightedResidue[]
  } = {},
): StructureSource {
  const mode = options.structureMode ?? 'monomer'
  const artifactId = mode === 'complex'
    ? candidate.complex_artifact_id
    : candidate.structure_artifact_id ?? candidate.complex_artifact_id
  const url = resolveApiUrl(options.downloadUrl)
  const configuredFormat = candidate.properties.structure_format
  const format = configuredFormat === 'mmcif' || configuredFormat === 'alphafold' ? configuredFormat : 'pdb'

  return {
    projectId: candidate.project_id,
    candidateId: candidate.id,
    url,
    format,
    proteinName: candidate.name,
    chains: options.metadata?.chains ?? candidateStrings(candidate, 'chains'),
    atomCount: options.metadata?.atom_count ?? null,
    ligands: options.metadata?.ligands,
    highlightedResidues: options.highlightedResidues,
    confidenceScore: candidateScore(candidate, 'plddt'),
    designScore: candidateScore(candidate, 'design_score') ?? candidateScore(candidate, 'interface_score') ?? candidate.score,
    artifactId: artifactId ?? undefined,
  }
}

export function structureSourceFromUrl(
  url: string | null | undefined,
  overrides: Partial<StructureSource> = {},
): StructureSource {
  return {
    url: url ?? null,
    format: overrides.format ?? inferFormatFromUrl(url),
    ...overrides,
  }
}

function inferFormatFromPath(path: string | null | undefined): StructureFormat {
  if (!path) return 'pdb'
  const lower = path.toLowerCase()
  if (lower.endsWith('.cif') || lower.endsWith('.mmcif')) return 'mmcif'
  if (lower.includes('alphafold') || lower.includes('af-')) return 'alphafold'
  return 'pdb'
}

function inferFormatFromUrl(url: string | null | undefined): StructureFormat {
  if (!url) return 'pdb'
  const lower = url.toLowerCase()
  if (lower.includes('.cif') || lower.includes('.mmcif')) return 'mmcif'
  if (lower.includes('alphafold') || lower.includes('af-')) return 'alphafold'
  return 'pdb'
}

export function parseHotspotResidue(
  residue: string,
  chainId?: string | null,
  residueIndex?: number | null,
): HighlightedResidue | null {
  const trimmed = residue.trim()
  if (!trimmed) return null

  const match = trimmed.match(/^([A-Za-z0-9]+):([A-Za-z]{1,3})(\d+)$/)
  if (match) {
    return {
      chainId: match[1],
      seq: Number.parseInt(match[3], 10),
      label: trimmed,
    }
  }

  if (chainId && residueIndex != null) {
    return { chainId, seq: residueIndex, label: trimmed }
  }

  return null
}
