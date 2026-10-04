import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Artifact } from '../../lib/schemas/artifact'
import type { Candidate } from '../../lib/schemas/candidate'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AlphaFoldResults } from './AlphaFoldResults'

const candidate: Candidate = {
  id: 'candidate-1',
  project_id: 'project-1',
  candidate_key: 'binder_design_0_mpnn_seq1',
  name: 'binder_design_0_mpnn_seq1',
  candidate_kind: 'design_candidate',
  status: 'scored',
  rank: 1,
  score: 1.9,
  scores: { plddt: 76.46, ptm: 0.512, mean_pae: 6.13 },
  properties: { route: 'reference_scaffold' },
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
    expect(screen.getByText('Available predictions · 1')).toBeInTheDocument()
    expect(screen.getAllByText('76.46')).toHaveLength(2)
    expect(screen.getByText(/Prediction metrics do not establish experimental binding activity/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PDB' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'JSON' })).toBeInTheDocument()
  })
  it('exposes imported complex structures and available interface metrics', () => {
    const download = vi.fn()
    const complex = artifact('complex-1', 'predicted_structure', 'complex.pdb', candidate.candidate_key)
    renderWithProviders(<AlphaFoldResults candidates={[{ ...candidate, structure_artifact_id: null,
      complex_artifact_id: 'complex-1', scores: { plddt: 93.2, iptm: 0.88, pae_interaction: 5.2, rosetta_interface_dg: -78 } }]}
      artifacts={[complex]} onDownload={download} />)
    fireEvent.click(screen.getByRole('button', { name: 'Complex PDB' }))
    expect(download).toHaveBeenCalledWith(complex)
    expect(screen.getByRole('link', { name: 'View structure' })).toHaveAttribute('href', '#/candidates?project=project-1&candidate=candidate-1')
    expect(screen.getByText('0.880')).toBeInTheDocument()
    expect(screen.getByText('-78.00')).toBeInTheDocument()
    expect(screen.queryByText(/1000/)).not.toBeInTheDocument()
  })
})
