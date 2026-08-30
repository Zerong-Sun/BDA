import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { PipelineRail } from './PipelineRail'

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    projectId: 'proj_ready',
    hasProject: true,
    activeProject: { id: 'proj_ready', name: 'Ready project' },
  }),
}))

vi.mock('../../lib/api/projects', () => ({
  getProjectOverview: vi.fn().mockResolvedValue({
    target_readiness: { ready_for_workflow: true },
    funnel: { generated: 4, ordered: 1 },
    experiment_result_count: 1,
  }),
}))

describe('PipelineRail route selection', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
  })

  afterEach(cleanup)

  it('selects Research from the route even when project progress is at Results', async () => {
    window.location.hash = '/research?project=proj_ready'
    renderWithProviders(<PipelineRail />)

    const research = screen.getByRole('tab', { name: /Research/i })
    const results = screen.getByRole('tab', { name: /Results/i })
    await waitFor(() => expect(results).toHaveTextContent('You are here'))

    expect(research).toHaveAttribute('aria-selected', 'true')
    expect(results).toHaveAttribute('aria-selected', 'false')
  })

  it('navigates to an unlocked earlier step and follows the new route selection', async () => {
    window.location.hash = '/results?project=proj_ready'
    renderWithProviders(<PipelineRail />)

    const workflow = screen.getByRole('tab', { name: /Workflow/i })
    const results = screen.getByRole('tab', { name: /Results/i })
    await waitFor(() => expect(results).toHaveTextContent('You are here'))
    expect(results).toHaveAttribute('aria-selected', 'true')

    fireEvent.click(workflow)

    await waitFor(() => expect(window.location.hash).toContain('/workflow?project=proj_ready'))
    expect(workflow).toHaveAttribute('aria-selected', 'true')
    expect(results).toHaveAttribute('aria-selected', 'false')
  })
})
