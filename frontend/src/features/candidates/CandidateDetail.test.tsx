import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { Candidate } from '../../lib/schemas/candidate'
import { CandidateDetail } from './CandidateDetail'

vi.mock('./CandidateConditionMetrics', () => ({ CandidateConditionMetrics: () => null }))
vi.mock('../research/AttachToGoalButton', () => ({ AttachToGoalButton: () => null }))

const candidate: Candidate = {
  id: 'candidate_detail', project_id: 'project_detail', candidate_key: 'DESIGN-001',
  name: 'A named binder', candidate_kind: 'design_candidate', status: 'generated',
  rank: null, score: null, scores: {}, properties: { family: 'Scaffold family A' },
  structure_artifact_id: null, complex_artifact_id: null, source_job_id: null,
  version: 1, created_at: '2026-09-30T00:00:00Z', updated_at: '2026-09-30T00:00:00Z',
}

describe('candidate identity in details', () => {
  beforeEach(() => useAppStore.setState({ language: 'en' }))
  afterEach(cleanup)

  it('shows the candidate name separately from its identifier and actual family', () => {
    renderWithProviders(<CandidateDetail candidate={candidate} projectId={candidate.project_id} />)
    expect(screen.getByRole('heading', { name: 'DESIGN-001' })).toBeInTheDocument()
    expect(screen.getByText('A named binder', { exact: true })).toBeInTheDocument()
    expect(screen.getByText('Family Scaffold family A. No next action specified.')).toBeInTheDocument()
    expect(screen.queryByText(/Family A named binder/)).not.toBeInTheDocument()
  })

  it('does not invent a family from the name when family metadata is missing', () => {
    renderWithProviders(<CandidateDetail candidate={{ ...candidate, properties: {} }} projectId={candidate.project_id} />)
    expect(screen.getByText('A named binder', { exact: true })).toBeInTheDocument()
    expect(screen.getByText('Family —. No next action specified.')).toBeInTheDocument()
  })
})
