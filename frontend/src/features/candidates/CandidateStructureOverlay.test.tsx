import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { Candidate } from '../../lib/schemas/candidate'
import { CandidateStructureOverlay } from './CandidateStructureOverlay'

const candidate: Candidate = {
  id: 'cand_a', project_id: 'proj_test', candidate_key: 'cand_a', name: 'binder_route', status: 'folded',
  rank: 1, score: 91,
  scores: { interface_score: 91, design_score: 91, pred_kd: '0.8 nM', plddt: 88, interface_pae: 4.2, rosetta_score: -18.5, solubility_score: 0.74 },
  properties: { decision: 'Review', next_action: 'Review structure and scoring provenance.', chains: ['A', 'B'] },
  structure_artifact_id: 'artifact_a', complex_artifact_id: 'artifact_complex_a', source_job_id: 'job_1',
  version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
}

describe('CandidateStructureOverlay', () => {
  it('shows chain roles, missing hotspot/contact evidence, and metric provenance', () => {
    renderWithProviders(
      <CandidateStructureOverlay candidate={candidate} projectId="proj_test" structureMode="complex"
        metadata={{ chains: ['A', 'B'], atom_count: 1200, chain_count: 2, residue_count: 240, ligands: [], format: 'pdb' }} />,
    )
    expect(screen.getByText('Structure interpretation overlay')).toBeInTheDocument()
    expect(screen.getByText('Candidate / binder chain (inferred)')).toBeInTheDocument()
    expect(screen.getByText('Target / partner chain (inferred)')).toBeInTheDocument()
    expect(screen.getByText(/No confirmed hotspot rows are linked/i)).toBeInTheDocument()
    expect(screen.getByText(/No computed residue-contact table is attached/i)).toBeInTheDocument()
    expect(screen.getByText('Candidate ranking record')).toBeInTheDocument()
  })
})
