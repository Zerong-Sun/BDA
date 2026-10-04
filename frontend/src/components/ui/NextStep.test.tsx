import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { getProjectOverview } from '../../lib/api/projects'
import { NextStep } from './NextStep'

vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ projectId: 'project-a', hasProject: true }) }))
vi.mock('../../lib/api/projects', () => ({ getProjectOverview: vi.fn() }))
beforeEach(() => useAppStore.setState({ language: 'en' }))
afterEach(cleanup)

describe('result next action', () => {
  it('does not announce a completed research cycle merely from opening an empty results page', async () => {
    vi.mocked(getProjectOverview).mockResolvedValue({ target_readiness: { ready_for_workflow: false }, funnel: { generated: 0, ordered: 0 }, candidate_count: 0, experiment_result_count: 0 } as never)
    renderWithProviders(<NextStep stage="results" />)
    expect(await screen.findByText('No results are available yet. Review project inputs and task progress.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review project' })).toHaveAttribute('href', '#/projects?project=project-a')
    expect(screen.queryByText(/completed|complete loop|next round/i)).not.toBeInTheDocument()
  })

  it('opens decisions for imported results even when execution readiness is incomplete', async () => {
    vi.mocked(getProjectOverview).mockResolvedValue({ target_readiness: { ready_for_workflow: false }, funnel: { generated: 0, ordered: 0 }, candidate_count: 0, experiment_result_count: 2 } as never)
    renderWithProviders(<NextStep stage="results" />)
    expect(await screen.findByRole('link', { name: 'Review project decisions' })).toHaveAttribute('href', '#/research?project=project-a&tab=timeline')
    expect(screen.queryByText(/completed|complete loop|next round/i)).not.toBeInTheDocument()
  })
})
