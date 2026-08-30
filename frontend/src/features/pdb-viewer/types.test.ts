import { describe, expect, it } from 'vitest'
import type { Candidate } from '../../lib/schemas/candidate'
import type { ProjectTargetStructure } from '../../lib/schemas/target'
import {
  hasStructureData,
  parseHotspotResidue,
  structureSourceFromCandidate,
  structureSourceFromTarget,
  structureSourceFromUrl,
} from './types'

const candidate: Candidate = {
  id: 'PD1Binder_c4361', project_id: 'proj_pd1_0423', candidate_key: 'PD1Binder_c4361',
  name: 'scaffold_a', status: 'validated', rank: 1, score: 94,
  scores: { interface_score: 94, design_score: 94, pred_kd: '0.6 nM', plddt: 92 },
  properties: { decision: 'Anchor' }, structure_artifact_id: 'artifact_structure',
  complex_artifact_id: 'artifact_complex', source_job_id: 'job_1', version: 1,
  created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
}

const target: ProjectTargetStructure = {
  target: { id: 'tgt_pd1', project_id: 'proj_pd1_0423', name: 'PD-1', sequence: null,
    uniprot_accession: null, organism: null, identity_status: 'confirmed',
    structure_artifact_id: 'artifact_pd1', structure_status: 'approved', version: 1,
    target_kind: 'protein' as const, chemical_identity: {},
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z' },
  structure: { target_id: 'tgt_pd1', structure_status: 'approved', current_artifact_id: 'artifact_pd1',
    approved_revision_id: null, latest_revision: null },
  artifact: { id: 'artifact_pd1', project_id: 'proj_pd1_0423', artifact_type: 'target_structure',
    filename: 'pd1.pdb', content_type: 'chemical/x-pdb', status: 'available', size_bytes: 1200,
    checksum_sha256: 'a'.repeat(64), lineage: { pdb_id: '4ZQK', atom_count: 1200, chains: ['A', 'B'] },
    version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
    download_url: '/api/v2/artifacts/artifact_pd1/content' },
}

describe('hasStructureData', () => {
  it('returns true when url or file is present', () => {
    expect(hasStructureData({ url: '/api/v2/artifacts/x.pdb' })).toBe(true)
    expect(hasStructureData({ file: new File(['ATOM'], 'x.pdb') })).toBe(true)
    expect(hasStructureData({})).toBe(false)
  })
})

describe('structureSourceFromCandidate', () => {
  it('maps monomer structure url and scores', () => {
    const source = structureSourceFromCandidate(candidate, {
      metadata: {
        chains: ['A'],
        atom_count: 500,
        chain_count: 1,
        residue_count: 120,
        ligands: [{ id: 'ZN', name: 'ZN' }],
      },
    })
    expect(source.candidateId).toBe(candidate.id)
    expect(source.url).toBeNull()
    expect(source.confidenceScore).toBe(92)
    expect(source.designScore).toBe(94)
    expect(source.chains).toEqual(['A'])
    expect(source.ligands).toEqual([{ id: 'ZN', name: 'ZN' }])
  })

  it('uses complex artifact url when requested', () => {
    const source = structureSourceFromCandidate(candidate, { structureMode: 'complex' })
    expect(source.url).toBeNull()
    expect(source.format).toBe('pdb')
  })
})

describe('structureSourceFromTarget', () => {
  it('maps target metadata and urls', () => {
    const source = structureSourceFromTarget(target, 'proj_pd1_0423', {
      highlightedResidues: [{ chainId: 'A', seq: 59 }],
    })
    expect(source.projectId).toBe('proj_pd1_0423')
    expect(source.proteinName).toBe('PD-1')
    expect(source.pdbId).toBe('4ZQK')
    expect(source.chains).toEqual(['A', 'B'])
    expect(source.highlightedResidues).toEqual([{ chainId: 'A', seq: 59 }])
  })
})

describe('structureSourceFromUrl', () => {
  it('infers mmcif format from url', () => {
    const source = structureSourceFromUrl('https://files.rcsb.org/1abc.cif')
    expect(source.format).toBe('mmcif')
  })
})

describe('parseHotspotResidue', () => {
  it('parses chain:residue syntax', () => {
    expect(parseHotspotResidue('A:TYR59')).toEqual({
      chainId: 'A',
      seq: 59,
      label: 'A:TYR59',
    })
  })

  it('falls back to explicit chain and index', () => {
    expect(parseHotspotResidue('TYR59', 'A', 59)).toEqual({
      chainId: 'A',
      seq: 59,
      label: 'TYR59',
    })
  })
})
