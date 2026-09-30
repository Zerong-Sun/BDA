import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkflowPage } from '../../app/Workflow'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'

const state = vi.hoisted(() => ({ projectId: 'project-a' }))
const api = vi.hoisted(() => ({
  current: vi.fn(), runs: vi.fn(), graph: vi.fn(), preflight: vi.fn(), create: vi.fn(),
  plan: vi.fn(), apply: vi.fn(), preview: vi.fn(), submit: vi.fn(), artifacts: vi.fn(),
  access: vi.fn(),
}))
vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({
  projectId: state.projectId, activeProject: { id: state.projectId, name: state.projectId, summary: 'Design a binder' },
}) }))
vi.mock('../../lib/hooks/useProjectTargetStructure', () => ({ useTargetReadiness: () => ({
  data: { ready_for_workflow: true, blockers: [] }, isSuccess: true, isError: false, refetch: vi.fn(),
}) }))
vi.mock('../../lib/api/projects', () => ({ getCurrentWorkflowRunOrNull: api.current, listProjectWorkflowRuns: api.runs, getProjectAccess: api.access }))
vi.mock('../../lib/api/workflow', () => ({ createWorkflowRun: api.create, getWorkflowGraph: api.graph,
  getWorkflowPreflight: api.preflight, submitWorkflowRun: api.submit, previewWorkflowNodeScript: api.preview,
  preflightBlockersFrom: () => [],
}))
vi.mock('../../lib/api/workflowGates', () => ({ listGates: async () => ({ items: [] }), saveConnections: vi.fn() }))
vi.mock('../../lib/api/copilot', () => ({ planRoute: api.plan, applyRoutePlan: api.apply }))
vi.mock('../../lib/api/artifacts', () => ({ listProjectArtifacts: api.artifacts }))
vi.mock('../../lib/api/registry', () => ({ listModelPlugins: async () => [], validateModelPlugin: vi.fn() }))
vi.mock('./WorkflowContextBar', () => ({ WorkflowContextBar: () => null }))
vi.mock('./WorkflowResourceSidebar', () => ({ WorkflowResourceSidebar: ({ artifacts }: { artifacts: Array<{ id: string }> }) => <div>{artifacts.map((artifact) => <span key={artifact.id}>{artifact.id}</span>)}</div> }))
vi.mock('./WorkflowCanvas', () => ({ WorkflowCanvas: ({ onNodeSelected }: { onNodeSelected: (id: string) => void }) => <><button onClick={() => onNodeSelected('node-1')}>Select node</button><button onClick={() => onNodeSelected('node-2')}>Select another node</button></> }))
vi.mock('./WorkflowInspector', () => ({ WorkflowInspector: ({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) => <div><button onClick={() => onDirtyChange(true)}>Edit parameter</button><button onClick={() => onDirtyChange(false)}>Save parameter</button></div> }))
vi.mock('./NodeBuilder', () => ({ NodeBuilder: ({ open }: { open: boolean }) => open ? <div>Manual node builder</div> : null }))
vi.mock('../../components/ui/NextStep', () => ({ NextStep: () => <div>Next step: candidates</div> }))

const node = { id: 'node-1', workflow_run_id: 'run-a', node_key: 'fold', execution_mode: 'dispatch',
  node_type: 'model', model_plugin: 'Fold', model_plugin_id: null, container_image: null, command: null,
  queue: null, status: 'draft', parameters: {}, configuration: {}, input_bindings: [], error_message: null,
  version: 1, created_at: '', updated_at: '' }
const run = { id: 'run-a', project_id: 'project-a', name: 'Existing route', status: 'draft', graph: {}, version: 1 }
const preflight = { allowed: true, blockers: [], warnings: [], checks: { compute_backend: 'docker' } }
function plan(objective = 'Design a binder') {
  return { mode: 'service', project_id: 'project-a', target: 'target', objective, constraints: {}, knowledge_context: [], analysis_trace: [],
    route_options: [{ route_id: 'route-1', label: 'Complete route', recommended: false, estimated_steps: 1, summary: 'Fold the input', rationale: [], risks: [], constraints: {},
      modules: [{ module_id: 'plugin-1', model_name: 'Fold', available: true, summary: 'Predict structure', default_parameters: {} }] }] }
}

beforeEach(() => {
  vi.clearAllMocks()
  state.projectId = 'project-a'
  window.location.hash = '/workflow?project=project-a'
  useAppStore.setState({ language: 'en', appMode: 'application', uiDensity: 'guided', workflowSeed: null })
  api.current.mockResolvedValue(run)
  api.runs.mockResolvedValue([run])
  api.graph.mockImplementation(async (id: string) => ({ workflow: { ...run, id }, nodes: [node], edges: [], layout: {} }))
  api.preflight.mockResolvedValue(preflight)
  api.plan.mockResolvedValue(plan())
  api.apply.mockResolvedValue({ workflow_run: { id: 'run-new' } })
  api.create.mockResolvedValue({ ...run, id: 'run-manual' })
  api.artifacts.mockResolvedValue([])
  api.access.mockResolvedValue({ role: 'owner', permissions: { read: true, write: true, compute: true } })
  api.preview.mockResolvedValue({ workflow_node_id: 'node-1', script: 'echo reviewed', review_fingerprint: 'fingerprint' })
})
afterEach(cleanup)

describe('workflow journey', () => {
  it('waits for permissions and keeps viewer controls read-only', async () => {
    let resolve!: (value: object) => void
    api.access.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    renderWithProviders(<WorkflowPage />)
    expect(await screen.findByRole('button', { name: 'New route' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
    await act(async () => resolve({ role: 'viewer', permissions: { read: true, write: false, compute: false } }))
    expect(await screen.findByText('You do not have edit access to this project.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'New route' }))
    expect(api.create).not.toHaveBeenCalled()
    expect(api.plan).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
  })

  it('requires compute permission separately from draft editing', async () => {
    api.access.mockResolvedValue({ role: 'researcher', permissions: { read: true, write: true, compute: false } })
    renderWithProviders(<WorkflowPage />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'New route' })).toBeEnabled())
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
  })

  it('keeps actions disabled on permission errors and provides a working retry', async () => {
    api.access.mockRejectedValueOnce(new Error('Access service unavailable'))
    renderWithProviders(<WorkflowPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Retry permission check' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'New route' })).toBeEnabled())
    expect(api.access).toHaveBeenCalledTimes(2)
  })

  it('opens route choice without creating a run, and closes it after applying the complete template', async () => {
    renderWithProviders(<WorkflowPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'New route' }))
    expect(api.create).not.toHaveBeenCalled()
    expect(screen.queryByText('Next step: candidates')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Plan routes' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Create workflow from selected route' }))
    await waitFor(() => expect(api.apply).toHaveBeenCalledWith(expect.objectContaining({ project_id: 'project-a', selected_module_ids: ['plugin-1'] })))
    await waitFor(() => expect(screen.queryByLabelText('Objective for this workflow')).not.toBeInTheDocument())
    expect(window.location.hash).toContain('run=run-new')
    expect(api.submit).not.toHaveBeenCalled()
  })

  it('opens the planner with a handed-off objective even when a workflow already exists', async () => {
    useAppStore.setState({ workflowSeed: { projectId: 'project-a', goal: 'Use the reviewed hotspot', source: 'research_review' } })
    renderWithProviders(<WorkflowPage />)
    expect(await screen.findByLabelText('Objective for this workflow')).toHaveValue('Use the reviewed hotspot')
    expect(api.create).not.toHaveBeenCalled()
  })

  it('explains unavailable template steps and keeps manual creation available', async () => {
    const unavailable = plan()
    unavailable.route_options[0].modules[0].available = false
    api.plan.mockResolvedValue(unavailable)
    renderWithProviders(<WorkflowPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'New route' }))
    fireEvent.click(screen.getByRole('button', { name: 'Plan routes' }))
    expect(await screen.findByText('Unavailable plugins: Fold')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create workflow from selected route' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Create a blank workflow manually' })).toBeEnabled()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('keeps new-route planning available after a completed run', async () => {
    api.graph.mockResolvedValue({ workflow: { ...run, status: 'succeeded' }, nodes: [node], edges: [], layout: {} })
    renderWithProviders(<WorkflowPage />)
    await screen.findByText('Next step: candidates')
    fireEvent.click(await screen.findByRole('button', { name: 'New route' }))
    expect(screen.getByRole('button', { name: 'Plan routes' })).toBeEnabled()
  })

  it('invalidates a plan when the objective changes while its request is pending', async () => {
    let resolve!: (value: ReturnType<typeof plan>) => void
    api.plan.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    renderWithProviders(<WorkflowPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'New route' }))
    fireEvent.click(screen.getByRole('button', { name: 'Plan routes' }))
    await waitFor(() => expect(resolve).toBeDefined())
    fireEvent.change(screen.getByLabelText('Objective for this workflow'), { target: { value: 'A different objective' } })
    await act(async () => resolve(plan()))
    expect(await screen.findByText('The objective changed. Generate a new route before creating the workflow.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create workflow from selected route' })).not.toBeInTheDocument()
  })

  it('clears project-local planning state and ignores a late response after a project switch', async () => {
    let resolve!: (value: ReturnType<typeof plan>) => void
    api.plan.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    const view = renderWithProviders(<WorkflowPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'New route' }))
    fireEvent.change(screen.getByLabelText('Objective for this workflow'), { target: { value: 'Private project A objective' } })
    fireEvent.click(screen.getByRole('button', { name: 'Plan routes' }))
    await waitFor(() => expect(resolve).toBeDefined())
    state.projectId = 'project-b'
    view.rerender(<WorkflowPage />)
    await act(async () => resolve(plan('Private project A objective')))
    fireEvent.click(await screen.findByRole('button', { name: 'New route' }))
    expect(screen.getByLabelText('Objective for this workflow')).toHaveValue('')
    expect(screen.queryByText('Complete route')).not.toBeInTheDocument()
  })

  it('never fetches a linked workflow until its project ownership has been established', async () => {
    window.location.hash = '/workflow?project=project-a&run=foreign-run'
    renderWithProviders(<WorkflowPage />)
    expect(await screen.findByText(/The run in this link is not part of this project/)).toBeInTheDocument()
    expect(api.graph).not.toHaveBeenCalledWith('foreign-run')
    expect(api.preflight).not.toHaveBeenCalledWith('foreign-run')
  })

  it('shows preflight failure and lets the user retry instead of silently disabling submit', async () => {
    api.preflight.mockRejectedValueOnce(new Error('Preflight service unavailable'))
    renderWithProviders(<WorkflowPage />)
    expect(await screen.findByText('Preflight service unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Run check again' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeEnabled())
  })

  it('requires saving node edits before preview and never submits on the initial review click', async () => {
    renderWithProviders(<WorkflowPage />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Select node' }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit parameter' }))
    fireEvent.click(screen.getByRole('button', { name: 'Select another node' }))
    expect(window.location.hash).toContain('node=node-1')
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
    expect(screen.getByText('This node has unsaved changes. Save them before reviewing submission.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save parameter' }))
    fireEvent.click(screen.getByRole('button', { name: 'Submit workflow' }))
    expect(await screen.findByRole('button', { name: 'Confirm and submit jobs' })).toBeInTheDocument()
    expect(api.submit).not.toHaveBeenCalled()
  })

  it('creates a manual draft without using the route planner and opens the node builder', async () => {
    api.current.mockResolvedValue(null)
    api.runs.mockResolvedValue([])
    renderWithProviders(<WorkflowPage />)
    const create = await screen.findByRole('button', { name: 'Create a blank workflow manually' })
    await waitFor(() => expect(create).toBeEnabled())
    fireEvent.click(create)
    expect(await screen.findByText('Manual node builder')).toBeInTheDocument()
    expect(api.plan).not.toHaveBeenCalled()
    expect(api.submit).not.toHaveBeenCalled()
  })
})
