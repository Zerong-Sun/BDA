import { act, cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { WorkflowCanvas } from './WorkflowCanvas'
import { defaultWorkflowNodes } from './workflowTypes'

const saveLayout = vi.hoisted(() => vi.fn())
vi.mock('../../lib/api/workflow', () => ({
  saveWorkflowLayout: saveLayout, addWorkflowNode: vi.fn(), getWorkflowGraph: vi.fn(),
}))
vi.mock('@xyflow/react', async (importOriginal) => ({
  ...await importOriginal<typeof import('@xyflow/react')>(),
  ReactFlow: ({ onNodeDragStop }: { onNodeDragStop: () => void }) => (
    <button type="button" onClick={onNodeDragStop}>Finish moving node</button>
  ),
}))

beforeEach(() => {
  vi.useFakeTimers()
  saveLayout.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('WorkflowCanvas pending layout saves', () => {
  it('saves the current editable workflow after dragging', async () => {
    renderWithProviders(<WorkflowCanvas workflowRunId="run-a" initialNodes={defaultWorkflowNodes} />)
    fireEvent.click(screen.getByRole('button', { name: 'Finish moving node' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(saveLayout).toHaveBeenCalledTimes(1)
    expect(saveLayout).toHaveBeenCalledWith('run-a', expect.objectContaining({
      nodes: defaultWorkflowNodes.map(node => ({ id: node.id, position: node.position })),
    }))
  })

  it('cancels a queued layout save when leaving the workspace', async () => {
    const view = renderWithProviders(<WorkflowCanvas workflowRunId="run-a" initialNodes={defaultWorkflowNodes} />)
    fireEvent.click(screen.getByRole('button', { name: 'Finish moving node' }))
    view.unmount()
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(saveLayout).not.toHaveBeenCalled()
  })

  it('cancels a queued layout save after the workflow becomes read-only', async () => {
    const view = renderWithProviders(<WorkflowCanvas workflowRunId="run-a" initialNodes={defaultWorkflowNodes} />)
    fireEvent.click(screen.getByRole('button', { name: 'Finish moving node' }))
    view.rerender(<WorkflowCanvas workflowRunId="run-a" initialNodes={defaultWorkflowNodes} readOnly />)
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(saveLayout).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Finish moving node' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(saveLayout).not.toHaveBeenCalled()
  })

  it('does not save the previous workflow after switching to another run', async () => {
    const view = renderWithProviders(<WorkflowCanvas workflowRunId="run-a" initialNodes={defaultWorkflowNodes} />)
    fireEvent.click(screen.getByRole('button', { name: 'Finish moving node' }))
    view.rerender(<WorkflowCanvas workflowRunId="run-b" initialNodes={defaultWorkflowNodes} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(saveLayout).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Finish moving node' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(saveLayout).toHaveBeenCalledWith('run-b', expect.anything())
  })
})
