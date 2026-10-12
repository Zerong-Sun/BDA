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
  id: 'manual-step', workflow_run_id: 'workflow-a', node_key: 'Review literature', execution_mode: 'manual',
  node_type: 'manual_review', model_plugin: '', model_plugin_id: null, container_image: null, command: null,
  queue: null, status: 'draft', configuration: {}, input_bindings: [], error_message: null, version: 1,
  parameters: { acceptance_criteria: 'Check the primary source.', evidence_id: 'preserved', review_status: 'pending_review' },
  created_at: '2026-10-12T00:00:00Z', updated_at: '2026-10-12T00:00:00Z',
}
const label = 'Inputs, sources and acceptance criteria'
beforeEach(() => { vi.resetAllMocks(); useAppStore.setState({ language: 'en', appMode: 'application' }) })
afterEach(cleanup)

describe('manual workflow review editing', () => {
  it('saves criteria with the original workflow version without recording completion or losing metadata', async () => {
    api.update.mockResolvedValue({ ...node, version: 2, parameters: { ...node.parameters, acceptance_criteria: 'Add controls.' } })
    renderWithProviders(<ManualReviewInspector node={node} workflowVersion={7} readOnly={false} />)
    expect(screen.getByRole('button', { name: 'Save review criteria' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText(label), { target: { value: ' Add controls. ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save review criteria' }))
    expect(await screen.findByRole('status')).toHaveTextContent('review remains pending')
    expect(api.update).toHaveBeenCalledWith('workflow-a', 'manual-step', { parameters: {
      ...node.parameters, acceptance_criteria: 'Add controls.', description: 'Add controls.', review_status: 'pending_review',
    } }, 7)
    expect(api.update.mock.calls[0][2]).not.toHaveProperty('status')
    expect(screen.getByRole('button', { name: 'Save review criteria' })).toBeDisabled()
  })
  it('retains local input and baseline during background updates, then explicitly reloads after a conflict', async () => {
    api.update.mockRejectedValue(new ApiError('Workflow changed', 412))
    const view = renderWithProviders(<ManualReviewInspector node={node} workflowVersion={7} readOnly={false} />)
    fireEvent.change(screen.getByLabelText(label), { target: { value: 'My unsaved review.' } })
    const latest = { ...node, version: 2, parameters: { ...node.parameters, acceptance_criteria: 'Other reviewer.' } }
    view.rerender(<ManualReviewInspector node={latest} workflowVersion={8} readOnly={false} />)
    expect(screen.getByLabelText(label)).toHaveValue('My unsaved review.')
    fireEvent.click(screen.getByRole('button', { name: 'Save review criteria' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Workflow changed')
    expect(api.update.mock.calls[0][3]).toBe(7)
    api.graph.mockResolvedValue({ workflow: { version: 8 }, nodes: [latest] })
    fireEvent.click(screen.getByRole('button', { name: 'Discard edits and load latest' }))
    await waitFor(() => expect(screen.getByLabelText(label)).toHaveValue('Other reviewer.'))
    fireEvent.change(screen.getByLabelText(label), { target: { value: 'Reviewed latest.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save review criteria' }))
    await waitFor(() => expect(api.update).toHaveBeenCalledTimes(2))
    expect(api.update.mock.calls[1][3]).toBe(8)
  })
  it.each(['read-only', 'missing-version', 'blank'])('blocks invalid writes: %s', (reason) => {
    renderWithProviders(<ManualReviewInspector node={node} workflowVersion={reason === 'missing-version' ? undefined : 7} readOnly={reason === 'read-only'} />)
    const input = screen.getByLabelText(label)
    if (reason === 'read-only') expect(input).toBeDisabled()
    else fireEvent.change(input, { target: { value: reason === 'blank' ? '  ' : 'New criteria.' } })
    expect(screen.getByRole('button', { name: 'Save review criteria' })).toBeDisabled()
    expect(api.update).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /script|submit|execute/i })).not.toBeInTheDocument()
  })
  it('reports a removed node on explicit reload and keeps the local text', async () => {
    api.graph.mockResolvedValue({ workflow: { version: 8 }, nodes: [] })
    renderWithProviders(<ManualReviewInspector node={node} workflowVersion={7} readOnly={false} />)
    fireEvent.change(screen.getByLabelText(label), { target: { value: 'Keep my notes.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Discard edits and load latest' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This step was removed')
    expect(screen.getByLabelText(label)).toHaveValue('Keep my notes.')
  })
})
