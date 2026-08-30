import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { JobStatusDrawer } from '../jobs/JobStatusDrawer'
import { ScriptAssetManager } from './ScriptAssetManager'
import { WorkflowInspector } from './WorkflowInspector'
import { WorkflowResourceSidebar } from './WorkflowResourceSidebar'

const api = vi.hoisted(() => ({
  getWorkflowPreflight: vi.fn(),
  getJobLogs: vi.fn(),
  listModelPlugins: vi.fn(),
  listScriptAssets: vi.fn(),
  listWorkflowJobs: vi.fn(),
}))

vi.mock('../../lib/api/registry', () => ({
  listModelPlugins: api.listModelPlugins,
  listScriptAssets: api.listScriptAssets,
  uploadScriptAsset: vi.fn(),
}))

vi.mock('../../lib/api/workflow', () => ({
  getWorkflowPreflight: api.getWorkflowPreflight,
  previewWorkflowNodeScript: vi.fn(),
  submitWorkflowNode: vi.fn(),
  updateWorkflowNode: vi.fn(),
}))

vi.mock('../../lib/api/jobs', () => ({
  cancelJob: vi.fn(),
  getJobLogs: api.getJobLogs,
  listWorkflowJobs: api.listWorkflowJobs,
  syncJobResult: vi.fn(),
}))

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'project_test' }),
}))

vi.mock('../copilot/ClusterDrafts', () => ({
  ClusterDrafts: () => null,
}))

afterEach(cleanup)

beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  api.getWorkflowPreflight.mockResolvedValue({ allowed: true, blockers: [], warnings: [], checks: {} })
  api.getJobLogs.mockResolvedValue({ logs: '' })
  api.listModelPlugins.mockResolvedValue([])
  api.listScriptAssets.mockResolvedValue([])
  api.listWorkflowJobs.mockResolvedValue([])
})

describe('workflow chrome safeguards', () => {
  it('propagates read-only state to artifact upload while keeping artifact reads available', async () => {
    renderWithProviders(
      <WorkflowResourceSidebar
        projectId="project_test"
        artifacts={[]}
        onArtifactUploaded={vi.fn()}
        onArtifactSelected={vi.fn()}
        readOnly
      />,
    )

    expect(await screen.findByRole('button', { name: 'Browse artifact files' })).toBeDisabled()
    expect(screen.getByText(/Upload target structures/i)).toBeInTheDocument()
  })

  it('blocks inspector parameter saving and manual node submission in read-only mode', async () => {
    renderWithProviders(
      <WorkflowInspector
        workflowRunId="run_test"
        readOnly
        selectedNode={{
          id: 'node_test', workflow_run_id: 'run_test', node_key: 'fold', node_type: 'model',
          model_plugin: 'test-plugin', model_plugin_id: null, container_image: null, command: null,
          queue: null, status: 'succeeded', parameters: {}, input_bindings: [], error_message: null, version: 1,
          created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
        }}
      />,
    )

    await waitFor(() => expect(screen.getByRole('button', { name: 'Save parameters' })).toBeDisabled())
    expect(screen.getByRole('button', { name: /Manual LSF submit/i })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Submit selected node' })).not.toBeInTheDocument()
  })

  it('hides the native script picker behind a localized registry trigger and names reorder handles', async () => {
    api.listScriptAssets.mockResolvedValueOnce([
      {
        id: 'script_test', name: 'submit.lsf', artifact_id: 'artifact_test', checksum_sha256: 'abc123',
        runtime: 'lsf', created_by: 'tester', version: 1,
        created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    renderWithProviders(<ScriptAssetManager />)

    await screen.findByText('submit.lsf')
    expect(screen.getByLabelText('Script file')).toHaveClass('hidden')
    expect(screen.getByRole('button', { name: 'Choose script file' })).toHaveAttribute('data-slot', 'button')
    expect(screen.getByRole('button', { name: 'Reorder script' })).toHaveAttribute(
      'data-slot',
      'sortable-item-handle',
    )
  })

  it('marks the log step complete when a job reports an error without fetched logs', async () => {
    api.listWorkflowJobs.mockResolvedValueOnce([
      {
        id: 'job_test', submission_id: 'submission_test', workflow_run_id: 'run_test', workflow_node_id: 'node_test',
        project_id: 'project_test', status: 'failed', compute_backend: 'lsf', model_plugin: 'test-plugin',
        attempt_number: 1, external_id: null, next_poll_at: null, timeout_at: null, error_code: 'FAILED',
        error_message: 'scheduler failure', version: 1,
        created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    renderWithProviders(<JobStatusDrawer workflowRunId="run_test" />)

    const job = await screen.findByRole('button', { name: /job_test/i })
    fireEvent.click(job)
    const logStep = await screen.findByText('scheduler failure')
    expect(logStep.closest('[data-slot="timeline-item"]')).toHaveAttribute('data-completed')
  })

  it('disables cancellation and result synchronization for a selected read-only job', async () => {
    api.listWorkflowJobs.mockResolvedValueOnce([
      {
        id: 'job_running', submission_id: 'submission_test', workflow_run_id: 'run_test', workflow_node_id: 'node_test',
        project_id: 'project_test', status: 'running', compute_backend: 'lsf', model_plugin: 'test-plugin',
        attempt_number: 1, external_id: 'lsf-123', next_poll_at: null, timeout_at: null, error_code: null,
        error_message: null, version: 1,
        created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    renderWithProviders(<JobStatusDrawer workflowRunId="run_test" readOnly />)

    fireEvent.click(await screen.findByRole('button', { name: /job_running/i }))
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Sync result' })).toBeDisabled()
  })
})
