import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { WorkflowContextBar } from './WorkflowContextBar'

vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ activeProject: { id: 'project', name: 'Project' } }) }))
vi.mock('../../lib/api/registry', () => ({ listComputeNodes: async () => [], getClusterHealth: async () => ({ connected: false }) }))
vi.mock('../../lib/api/health', () => ({ getHealth: async () => ({ status: 'ok' }) }))
afterEach(cleanup)

describe('organized route context', () => {
  it('shows a short method name, explanation and recoverable historical aliases', async () => {
    useAppStore.setState({ language: 'zh' })
    renderWithProviders(<WorkflowContextBar workflowRunId="run" projectWorkflowRuns={[{
      id: 'run', name: 'Legacy route', status: 'draft', graph: { route_presentation: {
        name: '支架改造', category: 'design', summary: '保留支架，比较变化。',
        method: '支架改造', objective: '比较假设', evidence: '尚无实验结果', next_step: '复核证据', aliases: ['Route A'],
      } },
    }]} onSelectRun={vi.fn()} />)
    expect(screen.getByTestId('route-explanation')).toHaveTextContent('尚无实验结果')
    expect(screen.getByText('支架改造 · draft')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看证据 →' })).toHaveAttribute('href', '#/research?project=project&tab=evidence')
    expect(screen.getByRole('link', { name: '待办复核 →' })).toHaveAttribute('href', '#/inbox?project=project')
    expect(screen.getByRole('link', { name: '项目结果与报告 →' })).toHaveAttribute('href', '#/research?project=project')
    expect(screen.getByRole('button', { name: '方法与目标' })).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(screen.getByRole('button', { name: '方法与目标' }))
    expect(screen.getByText('比较假设')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '旧名称与追溯' }))
    expect(await screen.findByText('Route A')).toBeVisible()
  })
})
