import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ResearchGapResolutionButton } from './ResearchGapResolutionButton'

const createResolution = vi.hoisted(() => vi.fn())
const waitForResolution = vi.hoisted(() => vi.fn())

vi.mock('../../lib/api/researchGaps', () => ({
  createResearchGapResolution: createResolution,
  waitForResearchGapResolution: waitForResolution,
}))

describe('ResearchGapResolutionButton', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    createResolution.mockReset().mockResolvedValue({
      operation_id: 'operation-one',
      research_target_id: 'target-one',
      status: 'pending',
    })
    waitForResolution.mockReset().mockResolvedValue({ status: 'succeeded' })
  })

  it('runs the write-backed gap resolution workflow', async () => {
    renderWithProviders(
      <ResearchGapResolutionButton
        projectId="project-one"
        researchTargetId="target-one"
        properties={{}}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Resolve data gaps' }))
    await waitFor(() => {
      expect(createResolution).toHaveBeenCalledWith('project-one', 'target-one')
      expect(waitForResolution).toHaveBeenCalledWith('operation-one')
    })
  })

  it('shows resolved data gaps separately from experimental gaps', () => {
    renderWithProviders(
      <ResearchGapResolutionButton
        projectId="project-one"
        researchTargetId="target-one"
        properties={{
          gap_resolution: {
            status: 'completed_with_remaining_scientific_gaps',
            items: [
              { id: 'predicted_structure', status: 'resolved_with_predicted_model' },
              { id: 'reference:R014', status: 'resolved' },
              { id: 'predicted_structure-review', kind: 'structure', status: 'requires_review' },
              { id: 'scientific_validation', status: 'requires_experiment' },
            ],
          },
        }}
      />,
    )
    expect(screen.getByText('All Gaps: Resolution Status')).toBeInTheDocument()
    expect(screen.getByText('Reference content R014 · Resolved')).toBeInTheDocument()
    expect(
      screen.getByText('predicted_structure-review · Requires molecular identity review'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Scientific validation gaps · Requires new evidence / experiment'),
    ).toBeInTheDocument()
  })
})
