import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DryLabDecisionTree } from './DryLabDecisionTree'

const api = vi.hoisted(() => ({ timeline: vi.fn(), goals: vi.fn() }))
vi.mock('../../lib/api/timeline', () => ({ listAllTimeline: api.timeline }))
vi.mock('../../lib/api/researchGoals', () => ({ listResearchGoals: api.goals }))
vi.mock('../timeline/DecisionTreeView', () => ({ DecisionTreeView: () => <div data-testid="duplicated-decision-tree" /> }))

beforeEach(() => {
  vi.clearAllMocks()
  useAppStore.setState({ language: 'en' })
  window.location.hash = '#/research?project=project-one&tab=methods'
})
afterEach(cleanup)

describe('method decision-record entry', () => {
  it.each([
    ['en', 'Reasoning behind method choices', 'Open decision record'],
    ['zh', '方法选择依据', '查看决策记录'],
  ] as const)('links to the canonical project decision record in %s without loading another tree', (language, heading, action) => {
    useAppStore.setState({ language })
    const { container } = renderWithProviders(<DryLabDecisionTree projectId="project-one" />)
    expect(screen.getByText(heading)).toBeVisible()
    expect(screen.getByRole('link', { name: action })).toHaveAttribute('href', '#/research?project=project-one&tab=timeline')
    expect(container.querySelector('[data-tour-id="dry-lab-decision-tree"]')).not.toBeNull()
    expect(screen.queryByTestId('duplicated-decision-tree')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show reasoning|展开推理/ })).not.toBeInTheDocument()
    expect(api.timeline).not.toHaveBeenCalled()
    expect(api.goals).not.toHaveBeenCalled()
  })

  it('navigates from methods to the same project’s timeline tab', () => {
    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)
    fireEvent.click(screen.getByRole('link', { name: 'Open decision record' }))
    expect(window.location.hash).toBe('#/research?project=project-one&tab=timeline')
  })

  it('offers project selection when no project is available', () => {
    renderWithProviders(<DryLabDecisionTree projectId="" />)
    expect(screen.getByRole('link', { name: 'Choose a project' })).toHaveAttribute('href', '#/projects')
    expect(api.timeline).not.toHaveBeenCalled()
    expect(api.goals).not.toHaveBeenCalled()
  })
})
