import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { WorkflowToolbar } from './WorkflowToolbar'

afterEach(cleanup)

const handlers = {
  onCreateRun: vi.fn(),
  onNewRoute: vi.fn(),
  onAddNode: vi.fn(),
  onStart: vi.fn(),
}

describe('WorkflowToolbar', () => {
  it('blocks submission when execution preflight has not passed without locking DAG editing', () => {
    renderWithProviders(
      <WorkflowToolbar
        {...handlers}
        isDemoMode={false}
        readOnly={false}
        workflowRunId="run_test"
        createPending={false}
        startPending={false}
        submitDisabled
      />,
    )

    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Add workflow node' })).toBeEnabled()
  })

  it('enables submission after execution preflight passes', () => {
    renderWithProviders(
      <WorkflowToolbar
        {...handlers}
        isDemoMode={false}
        readOnly={false}
        workflowRunId="run_test"
        createPending={false}
        startPending={false}
        submitDisabled={false}
      />,
    )

    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeEnabled()
  })
})
