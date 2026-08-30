import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Artifact } from '../../lib/schemas/artifact'
import type { Candidate } from '../../lib/schemas/candidate'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { RosettaResults } from './RosettaResults'

const baseCandidate: Candidate = {
  id: 'candidate-1',
  project_id: 'project-1',
  candidate_key: 'route_a_design_1_mpnn_seq1',
  name: 'route_a_design_1_mpnn_seq1',
  candidate_kind: 'design_candidate',
  status: 'scored',
  rank: 1,
  score: -3.1,
  scores: {
    rosetta_score: -310,
    rosetta_score_per_residue: -3.1,
    proteinmpnn_score: 1.2,
  },
  properties: { route: 'route_a', residue_count: 100 },
  structure_artifact_id: null,
  complex_artifact_id: null,
  source_job_id: null,
  version: 1,
  created_at: '2026-07-27T00:00:00Z',
  updated_at: '2026-07-27T00:00:00Z',
}

const scoreArtifact: Artifact = {
  id: 'artifact-1',
  project_id: 'project-1',
  artifact_type: 'score_table',
  filename: 'project_rosetta_scores.csv',
  content_type: 'text/csv',
  status: 'available',
  size_bytes: 100,
  checksum_sha256: 'abc',
  lineage: { source: 'manual_cluster_import', method: 'Rosetta' },
  version: 1,
  created_at: '2026-07-27T00:00:00Z',
  updated_at: '2026-07-27T00:00:00Z',
  download_url: '/download',
}

describe('RosettaResults', () => {
  beforeEach(() => useAppStore.setState({ language: 'en' }))
  afterEach(() => cleanup())

  it('shows scored designs, routes, score semantics, and registered artifacts', () => {
    const onDownload = vi.fn()
    const routeB: Candidate = {
      ...baseCandidate,
      id: 'candidate-2',
      candidate_key: 'route_b_design_1_mpnn_seq1',
      name: 'route_b_design_1_mpnn_seq1',
      rank: 2,
      properties: { route: 'route_b', residue_count: 101 },
      scores: { rosetta_score: -300, rosetta_score_per_residue: -2.97 },
    }

    renderWithProviders(
      <RosettaResults
        candidates={[routeB, baseCandidate]}
        artifacts={[scoreArtifact]}
        onDownload={onDownload}
      />,
    )

    expect(screen.getByText('Rosetta computational scores')).toBeInTheDocument()
    expect(screen.getByText('route_a_design_1_mpnn_seq1')).toBeInTheDocument()
    expect(screen.getByText('route_b_design_1_mpnn_seq1')).toBeInTheDocument()
    expect(screen.getAllByText('route_a').length).toBeGreaterThan(0)
    expect(screen.getAllByText('route_b').length).toBeGreaterThan(0)
    expect(screen.getByText(/Lower Rosetta energy scores are better/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /project_rosetta_scores.csv/ })).toBeInTheDocument()
  })
})
