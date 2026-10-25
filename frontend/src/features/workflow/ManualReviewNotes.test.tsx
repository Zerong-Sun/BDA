import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ManualReviewInspector } from './ManualReviewInspector'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import { ApiError } from '../../lib/api/client'

const api = vi.hoisted(() => ({ update: vi.fn(), graph: vi.fn() }))
vi.mock('../../lib/api/workflow', () => ({ updateWorkflowNode: api.update, getWorkflowGraph: api.graph }))
const node: WorkflowNode = {
  id: 'step', workflow_run_id: 'workflow', node_key: 'Review', execution_mode: 'manual',
  node_type: 'manual_review', model_plugin: '', model_plugin_id: null, container_image: null, command: null,
  queue: null, status: 'draft', configuration: {}, input_bindings: [], error_message: null, version: 1,
  parameters: { acceptance_criteria: 'Inspect sources.', review_notes: 'Original observations.', review_status: 'pending_review' },
  created_at: '2026-10-14T00:00:00Z', updated_at: '2026-10-14T00:00:00Z',
}
const notesLabel = 'Step observations and conclusions'
beforeEach(() => { vi.resetAllMocks(); useAppStore.setState({ language: 'en', appMode: 'application' }) })
afterEach(cleanup)

describe('versioned manual review observations', () => {
  it('retains unsaved notes during background changes and uses the original expected version', async () => {
    api.update.mockRejectedValue(new ApiError('Workflow changed', 412))
    const view = renderWithProviders(<ManualReviewInspector node={node} workflowVersion={3} readOnly={false} />)
    fireEvent.change(screen.getByLabelText(notesLabel), { target: { value: 'My new observations.' } })
    const newer = { ...node, version: 2, parameters: { ...node.parameters, review_notes: 'Other reviewer.' } }
    view.rerender(<ManualReviewInspector node={newer} workflowVersion={4} readOnly={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save review criteria' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Workflow changed')
    expect(api.update.mock.calls[0][3]).toBe(3)
    expect(screen.getByLabelText(notesLabel)).toHaveValue('My new observations.')
    api.graph.mockResolvedValue({ workflow: { version: 4 }, nodes: [newer] })
    fireEvent.click(screen.getByRole('button', { name: 'Discard edits and load latest' }))
    await waitFor(() => expect(screen.getByLabelText(notesLabel)).toHaveValue('Other reviewer.'))
  })

  it('locks an existing draft immediately when edit permission is removed', () => {
    const view = renderWithProviders(<ManualReviewInspector node={node} workflowVersion={3} readOnly={false} />)
    fireEvent.change(screen.getByLabelText(notesLabel), { target: { value: 'Unsaved observations.' } })
    view.rerender(<ManualReviewInspector node={node} workflowVersion={3} readOnly />)
    expect(screen.getByLabelText(notesLabel)).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save review criteria' })).toBeDisabled()
    expect(api.update).not.toHaveBeenCalled()
  })
})
