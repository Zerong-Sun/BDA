import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Artifact } from '../../lib/schemas/artifact'
import type { Candidate } from '../../lib/schemas/candidate'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AlphaFoldResults } from './AlphaFoldResults'

const candidate: Candidate = {
  id: 'candidate-1',
  project_id: 'project-1',
  candidate_key: 'brazzein_design_0_mpnn_seq1',
  name: 'brazzein_design_0_mpnn_seq1',
  candidate_kind: 'design_candidate',
  status: 'scored',
  rank: 1,
  score: 1.9,
  scores: { plddt: 76.46, ptm: 0.512, mean_pae: 6.13 },
  properties: { route: 'brazzein' },
  structure_artifact_id: 'structure-1',
  complex_artifact_id: null,
  source_job_id: null,
  version: 2,
  created_at: '2026-07-27T00:00:00Z',
  updated_at: '2026-07-28T00:00:00Z',
}

function artifact(
  id: string,
  artifactType: string,
  filename: string,
  candidateKey: string | null,
): Artifact {
  return {
    id,
    project_id: 'project-1',
    artifact_type: artifactType,
    filename,
    content_type: 'application/octet-stream',
    status: 'available',
    size_bytes: 100,
    checksum_sha256: 'abc',
    lineage: {
      source: 'historical_alphafold_import',
      method: 'AlphaFold2',
      candidate_key: candidateKey,
    },
    version: 1,
    created_at: '2026-07-28T00:00:00Z',
    updated_at: '2026-07-28T00:00:00Z',
    download_url: '/download',
  }
}

describe('AlphaFoldResults', () => {
  beforeEach(() => useAppStore.setState({ language: 'en' }))
  afterEach(() => cleanup())

  it('shows metric semantics, partial coverage, analysis, and raw result downloads', () => {
    renderWithProviders(
      <AlphaFoldResults
        candidates={[candidate]}
        artifacts={[
          artifact('structure-1', 'predicted_structure', 'model.pdb', candidate.candidate_key),
          artifact('confidence-1', 'confidence_record', 'confidence.json', candidate.candidate_key),
          artifact('summary-1', 'score_table', 'alphafold2_confidence.csv', null),
        ]}
        onDownload={vi.fn()}
      />,
    )

    expect(screen.getByText('AlphaFold structure confidence')).toBeInTheDocument()
    expect(screen.getByText('Partial coverage · 1/1000')).toBeInTheDocument()
    expect(screen.getAllByText('76.46')).toHaveLength(2)
    expect(screen.getByText(/monomer mean PAE is not interface PAE/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PDB' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'JSON' })).toBeInTheDocument()
  })
})
