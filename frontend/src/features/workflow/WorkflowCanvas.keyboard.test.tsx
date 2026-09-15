import { cleanup, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { WorkflowCanvas } from './WorkflowCanvas'
import { defaultWorkflowEdges, defaultWorkflowNodes } from './workflowTypes'

/**
 * A keyboard user must be able to do what a mouse user does on the canvas:
 * pick a node so the inspector opens, and put it down again. React Flow makes
 * nodes focusable and selects them on Enter, but only inside its own store -
 * these tests pin that the selection reaches the page.
 */

afterEach(cleanup)

function renderCanvas(props: { selectedNodeId?: string | null } = {}) {
  const onNodeSelected = vi.fn()
  const view = renderWithProviders(
    <WorkflowCanvas
      initialNodes={defaultWorkflowNodes}
      initialEdges={defaultWorkflowEdges}
      readOnly
      onNodeSelected={onNodeSelected}
      {...props}
    />,
  )
  return { ...view, onNodeSelected }
}

async function nodeElement(container: HTMLElement, id: string) {
  return waitFor(() => {
    const element = container.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"]`)
    if (!element) throw new Error(`node ${id} not rendered`)
    return element
  })
}

describe('WorkflowCanvas keyboard selection', () => {
  const firstId = defaultWorkflowNodes[0].id

  it('reports a node selected with Enter, as a click would', async () => {
    const { container, onNodeSelected } = renderCanvas()

    fireEvent.keyDown(await nodeElement(container, firstId), { key: 'Enter' })

    expect(onNodeSelected).toHaveBeenCalledWith(firstId)
  })

  it('clears the selection with Escape', async () => {
    const { container, onNodeSelected } = renderCanvas()

    fireEvent.keyDown(await nodeElement(container, firstId), { key: 'Escape' })

    expect(onNodeSelected).toHaveBeenCalledWith(null)
  })

  it('highlights the node the page says is selected, for a linked node', async () => {
    const { container } = renderCanvas({ selectedNodeId: firstId })

    const element = await nodeElement(container, firstId)

    await waitFor(() => expect(element).toHaveClass('selected'))
  })
})
