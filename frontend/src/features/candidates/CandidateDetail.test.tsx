import { act, cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { Candidate } from '../../lib/schemas/candidate'
import { CandidateDetail } from './CandidateDetail'

vi.mock('./CandidateConditionMetrics', () => ({ CandidateConditionMetrics: () => null }))
vi.mock('../research/AttachToGoalButton', () => ({ AttachToGoalButton: () => null }))
const api = vi.hoisted(() => ({ writable: true, promote: vi.fn(), explain: vi.fn() }))
vi.mock('../../lib/hooks/useProjectAccess', () => ({ useProjectAccess: () => ({ data: { permissions: { write: api.writable } } }) }))
vi.mock('../../lib/api/wetlab', () => ({ promoteCandidateToBench: api.promote }))
vi.mock('../../lib/api/copilot', () => ({ explainCandidate: api.explain }))
vi.mock('../../components/ui/InterpretationCard', () => ({ InterpretationCard: ({ reasoning }: { reasoning: { summary: string } }) => <p>{reasoning.summary}</p> }))

const candidate: Candidate = {
  id: 'candidate_detail', project_id: 'project_detail', candidate_key: 'DESIGN-001',
  name: 'A named binder', candidate_kind: 'design_candidate', status: 'generated',
  rank: null, score: null, scores: {}, properties: { family: 'Scaffold family A' },
  structure_artifact_id: null, complex_artifact_id: null, source_job_id: null,
  version: 1, created_at: '2026-09-30T00:00:00Z', updated_at: '2026-09-30T00:00:00Z',
}

describe('candidate identity in details', () => {
  beforeEach(() => { vi.resetAllMocks(); api.writable = true; useAppStore.setState({ language: 'en', appMode: 'application' }) })
  afterEach(cleanup)

  it.each(['viewer', 'demo', 'foreign-project'])('prevents bench promotion for %s', (reason) => {
    api.writable = reason !== 'viewer'
    if (reason === 'demo') useAppStore.setState({ appMode: 'demo' })
    renderWithProviders(<CandidateDetail candidate={{ ...candidate, properties: { sequence: 'ACD' } }} projectId={reason === 'foreign-project' ? 'other' : candidate.project_id} />)
    const button = screen.getByRole('button', { name: 'Send to bench' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(api.promote).not.toHaveBeenCalled()
  })

  it('does not display an earlier candidate explanation after changing selection', async () => {
    let resolve!: (value: { summary: string }) => void
    api.explain.mockImplementation(() => new Promise((done) => { resolve = done }))
    const view = renderWithProviders(<CandidateDetail candidate={candidate} projectId={candidate.project_id} />)
    fireEvent.click(screen.getByRole('button', { name: /explain/i }))
    view.rerender(<CandidateDetail candidate={{ ...candidate, id: 'different', candidate_key: 'DESIGN-002' }} projectId={candidate.project_id} />)
    await act(async () => resolve({ summary: 'Only applies to DESIGN-001' }))
    expect(screen.queryByText('Only applies to DESIGN-001')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'DESIGN-002' })).toBeInTheDocument()
  })

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
