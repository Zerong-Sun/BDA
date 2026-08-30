import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { ExperimentsPage } from './Experiments'
import { ResearchPage } from './Research'
import { WorkflowPage } from './Workflow'
import { CandidatesPage } from './Candidates'
import { ResultsPage } from './Results'

vi.mock('../features/pdb-viewer/StructureViewerLazy', () => ({
  StructureViewerLazy: () => <div data-testid="mock-structure-viewer">3D viewer lazy boundary</div>,
}))

vi.mock('../features/workflow/WorkflowCanvas', () => ({
  WorkflowCanvas: vi.fn(({ workflowRunId, readOnly }: { workflowRunId?: string; readOnly?: boolean }) => (
    <div data-testid="mock-workflow-canvas">
      Workflow canvas {workflowRunId ?? 'draft'} {readOnly ? 'read-only' : 'editable'}
    </div>
  )),
}))

function envelope<T>(data: T) {
  return HttpResponse.json(data as never)
}

const project = {
  id: 'proj_layer8',
  organization_id: 'org_test',
  name: 'Binder Design MVP',
  project_type: 'binder_design',
  status: 'active',
  owner_id: 'user_test',
  summary: 'Design a binder through an acceptance-tested route.',
  primary_target_id: null,
  version: 1,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const readinessBlocked = {
  stage: 'identity_confirmation',
  ready_for_workflow: false,
  blockers: ['target_identity_confirmation_required'],
  next_action: 'Confirm target identity',
  target_id: null,
  structure_artifact_id: null,
  identity_status: null,
  structure_status: null,
}

const readinessReady = {
  stage: 'approved',
  ready_for_workflow: true,
  blockers: [],
  next_action: 'Workflow may be planned',
  target_id: 'target_layer8',
  structure_artifact_id: null,
  identity_status: 'confirmed',
  structure_status: 'approved',
}

function installBaseHandlers(readiness: typeof readinessBlocked | typeof readinessReady = readinessBlocked) {
  server.use(
    http.get('/api/v2/projects', () =>
      envelope({
        items: [project],
        next_cursor: null,
      }),
    ),
    http.get('/api/v2/projects/proj_layer8/overview', () =>
      envelope({
        project,
        funnel: { generated: 0, designed: 0, folded: 0, scored: 0, ordered: 0 },
        candidate_count: 0,
        experiment_result_count: 0,
        available_artifact_count: 0,
        active_job_count: 0,
        latest_workflow_id: null,
        next_action: readiness.next_action,
        target: null,
        target_readiness: readiness,
      }),
    ),
    http.get('/api/v2/projects/proj_layer8/target-readiness', () => envelope(readiness)),
    http.get('/api/v2/projects/proj_layer8/primary-target', () =>
      readiness === readinessReady
        ? HttpResponse.json({ id: 'target_layer8', project_id: 'proj_layer8', name: 'Reference target',
          structure_artifact_id: null, structure_status: 'approved', identity_status: 'confirmed', version: 1 })
        : HttpResponse.json({ detail: 'Project has no primary target' }, { status: 404 }),
    ),
    http.get('/api/v2/projects/proj_layer8/research-summary', () =>
      envelope({
        brief: null,
        findings: [],
        literature_document_count: 0,
        intelligence_run_count: 0,
        knowledge_entry_count: 0,
      }),
    ),
    http.get('/api/v2/projects/proj_layer8/research-workspace', () =>
      envelope({
        project: {
          id: 'proj_layer8',
          name: { en: project.name, default: project.name },
          summary: { en: project.summary, default: project.summary },
          project_type: project.project_type,
          source_package_id: null,
          source_project_key: null,
          package: {},
          primary_target: null,
        },
        review_document: null,
        review_sections: [],
        graph_nodes: [],
        graph_edges: [],
        references: [],
        structures: [],
        research_targets: [],
        methods: [],
        datasets: [],
        counts: {},
      }),
    ),
    http.get('/api/v2/artifacts', () =>
      envelope({ items: [], next_cursor: null }),
    ),
    http.get('/api/v2/registry', () =>
      envelope({ items: [], next_cursor: null }),
    ),
    http.get('/api/v2/registry/script-assets', () => envelope([])),
    http.get('/api/v2/compute-drafts', () => envelope({ items: [], next_cursor: null })),
    http.get('/api/v2/projects/proj_layer8/knowledge', () => envelope({ items: [], next_cursor: null })),
    http.get('/api/v2/workflow-runs/run_layer8/jobs', () => envelope({ items: [], next_cursor: null })),
  )
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  // Entered through the /experiments alias on purpose: passing here is the
  // redirect to /projects working end to end.
  window.location.hash = '/experiments?project=proj_layer8'
  useAppStore.setState({
    activeProjectId: 'proj_layer8',
    appMode: 'application',
    language: 'en',
    uiDensity: 'guided',
  })
})

afterEach(cleanup)

describe('Layer 8 product contract pages', () => {
  it('Experiments shows the selected project and routes blocked users to target readiness repair', async () => {
    localStorage.setItem('bda_intro_dismissed', 'true')
    installBaseHandlers(readinessBlocked)

    renderWithProviders(<ExperimentsPage />)

    expect((await screen.findAllByText('Binder Design MVP')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Confirm target identity')).length).toBeGreaterThan(0)
    const readinessLinks = screen.getAllByRole('link', { name: 'Resolve target readiness' })
    expect(readinessLinks.length).toBeGreaterThan(0)
    expect(readinessLinks.every((link) =>
      link.getAttribute('href') === '#/research?tab=structures&project=proj_layer8',
    )).toBe(true)
  })

  it('Research target intelligence exposes the target confirmation gate before workflow planning', async () => {
    window.location.hash = '/research?tab=structures&project=proj_layer8'
    installBaseHandlers(readinessBlocked)

    renderWithProviders(<ResearchPage />)

    fireEvent.click(await screen.findByText('Target confirmation, structure import, and preparation'))
    expect(await screen.findByRole('heading', { name: 'Analyze a target' })).toBeInTheDocument()
    expect(screen.getByLabelText('Target')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyze target' })).toBeDisabled()
    expect(screen.getByText('Evidence levels')).toBeInTheDocument()
  })

  it('Workflow editor locks route submission until target readiness is server-approved', async () => {
    window.location.hash = '/workflow?project=proj_layer8'
    installBaseHandlers(readinessBlocked)
    const workflowRun = {
      id: 'run_layer8',
      project_id: 'proj_layer8',
      name: 'Binder design route',
      status: 'draft',
      graph: { nodes: [], edges: [], layout: {} },
      version: 1,
      created_by: 'user_test',
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    }
    server.use(
      http.get('/api/v2/projects/proj_layer8/workflow-runs', () =>
        envelope({ items: [workflowRun] }),
      ),
      http.get('/api/v2/workflow-runs/run_layer8/graph', () =>
        envelope({
          workflow: workflowRun,
          nodes: [],
          edges: [],
          layout: {},
        }),
      ),
      http.get('/api/v2/workflow-runs/run_layer8/preflight', () =>
        envelope({
          stage: 'workflow',
          allowed: false,
          project_id: 'proj_layer8',
          workflow_run_id: 'run_layer8',
          node_run_id: null,
          blockers: [{ code: 'target_not_ready', message: 'Target readiness is not approved.' }],
          warnings: [],
          checks: {},
        }),
      ),
    )

    renderWithProviders(<WorkflowPage />)

    expect(await screen.findByText('Target preparation is incomplete')).toBeInTheDocument()
    const readinessLinks = screen.getAllByRole('link', { name: 'Resolve target readiness' })
    expect(readinessLinks.length).toBeGreaterThan(0)
    expect(readinessLinks.every((link) =>
      link.getAttribute('href') === '#/research?tab=structures&project=proj_layer8',
    )).toBe(true)
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
  })

  it('Workflow editor goes read-only once the run reaches a terminal status', async () => {
    // Regression: the gate compared against 'completed', which this API never returns -
    // the branch was dead, so a finished run stayed fully editable. See core.statuses.
    window.location.hash = '/workflow?project=proj_layer8'
    installBaseHandlers(readinessReady)
    const workflowRun = {
      id: 'run_layer8',
      project_id: 'proj_layer8',
      name: 'Binder design route',
      status: 'succeeded',
      graph: { nodes: [], edges: [], layout: {} },
      version: 4,
      created_by: 'user_test',
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    }
    server.use(
      http.get('/api/v2/projects/proj_layer8/workflow-runs', () =>
        envelope({ items: [workflowRun] }),
      ),
      http.get('/api/v2/workflow-runs/run_layer8/graph', () =>
        envelope({ workflow: workflowRun, nodes: [], edges: [], layout: {} }),
      ),
      http.get('/api/v2/workflow-runs/run_layer8/preflight', () =>
        envelope({
          stage: 'workflow',
          allowed: true,
          project_id: 'proj_layer8',
          workflow_run_id: 'run_layer8',
          node_run_id: null,
          blockers: [],
          warnings: [],
          checks: {},
        }),
      ),
    )

    renderWithProviders(<WorkflowPage />)

    expect(await screen.findByText(/Workflow canvas .* read-only/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit workflow' })).toBeDisabled()
  })

  it('Workflow preflight names the offending node and keeps one line per unproven plugin', async () => {
    // Regression: blockers were read for a `workflow_node_id` the API never sends, so
    // "Required input port 'input_path' has no binding" appeared with no clue which stage
    // it belonged to; and plugin warnings were keyed on `code` alone, which collides now
    // that the same code is reported once per plugin.
    window.location.hash = '/workflow?project=proj_layer8'
    installBaseHandlers(readinessReady)
    const workflowRun = {
      id: 'run_layer8',
      project_id: 'proj_layer8',
      name: 'Scorer calibration',
      status: 'draft',
      graph: { nodes: [], edges: [], layout: {} },
      version: 2,
      created_by: 'user_test',
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    }
    server.use(
      http.get('/api/v2/projects/proj_layer8/workflow-runs', () =>
        envelope({ items: [workflowRun] }),
      ),
      http.get('/api/v2/workflow-runs/run_layer8/graph', () =>
        envelope({ workflow: workflowRun, nodes: [], edges: [], layout: {} }),
      ),
      http.get('/api/v2/workflow-runs/run_layer8/preflight', () =>
        envelope({
          stage: 'workflow',
          allowed: false,
          project_id: 'proj_layer8',
          workflow_run_id: 'run_layer8',
          node_run_id: null,
          blockers: [
            {
              code: 'input_binding_unsatisfied',
              message: "Required input port 'input_path' has no binding",
              node_key: 'route_0_mutant_modelling',
              port: 'input_path',
            },
          ],
          warnings: [
            {
              code: 'plugin_runtime_unproven',
              message: "Plugin 'Boltz' has never been observed to run correctly",
              plugin_key: 'Boltz',
            },
            {
              code: 'plugin_runtime_unproven',
              message: "Plugin 'RFdiffusion' has never been observed to run correctly",
              plugin_key: 'RFdiffusion',
            },
          ],
          checks: {},
        }),
      ),
    )

    renderWithProviders(<WorkflowPage />)

    expect(
      await screen.findByText(
        /route_0_mutant_modelling: Required input port 'input_path' has no binding/,
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/Plugin 'Boltz' has never been observed/)).toBeInTheDocument()
    expect(screen.getByText(/Plugin 'RFdiffusion' has never been observed/)).toBeInTheDocument()
  })

  it('Workflow lets an admin validate a declaration without clearing runtime-proof warnings', async () => {
    window.location.hash = '/workflow?project=proj_layer8'
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'admin', username: 'admin' }))
    installBaseHandlers(readinessReady)
    let validated = false
    let pluginRequests = 0
    let preflightRequests = 0
    const workflowRun = {
      id: 'run_layer8', project_id: 'proj_layer8', name: 'Plugin validation', status: 'draft',
      graph: { nodes: [], edges: [], layout: {} }, version: 1, created_by: 'user_test',
      created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
    }
    const modelPlugin = () => ({
      id: 'plugin-rfd', plugin_key: 'RFdiffusion', plugin_version: '1.1.0', name: 'RFdiffusion',
      container_image: '/work/rfd', command: 'run', parameter_schema: {}, output_schema: {},
      enabled: true, validation_status: validated ? 'valid' : 'unknown', validated_at: null,
      validation_errors: [], runtime_validation_status: 'unproven', runtime_validated_at: null,
      runtime_validation_evidence: {}, version: validated ? 2 : 1,
      created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      input_ports: [], output_ports: [], resources: {}, runtime_mode: 'conda',
      runtime_setup: [], output_parser: null, input_adapter: null,
    })
    const pluginNode = {
      id: 'node-rfd', workflow_run_id: 'run_layer8', node_key: 'rfd', node_type: 'model',
      model_plugin: 'RFdiffusion', model_plugin_id: 'plugin-rfd', container_image: null,
      command: null, queue: null, status: 'draft', parameters: {}, input_bindings: [],
      error_message: null, version: 1, created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    }
    server.use(
      http.get('/api/v2/projects/proj_layer8/workflow-runs', () => envelope({ items: [workflowRun] })),
      http.get('/api/v2/workflow-runs/run_layer8/graph', () =>
        envelope({ workflow: workflowRun, nodes: [pluginNode], edges: [], layout: {} })),
      http.get('/api/v2/registry/model-plugins', () => {
        pluginRequests += 1
        return envelope({
          items: [
            { ...modelPlugin(), id: 'plugin-rfd-old', plugin_version: '1.0.0' },
            modelPlugin(),
          ],
          next_cursor: null,
        })
      }),
      http.get('/api/v2/workflow-runs/run_layer8/preflight', () => {
        preflightRequests += 1
        return envelope({
          stage: 'workflow', allowed: true, project_id: 'proj_layer8', workflow_run_id: 'run_layer8',
          node_run_id: null, blockers: [],
          warnings: [
            ...(!validated ? [{
              code: 'plugin_unvalidated',
              message: "Plugin 'RFdiffusion' declaration status is 'unknown'; run registry validation",
              plugin_key: 'RFdiffusion',
              plugin_id: 'plugin-rfd',
              plugin_version: '1.1.0',
            }] : []),
            {
              code: 'plugin_runtime_unproven',
              message: "Plugin 'RFdiffusion' has no current runtime proof for this declaration",
              plugin_key: 'RFdiffusion',
              plugin_id: 'plugin-rfd',
              plugin_version: '1.1.0',
            },
          ], checks: {},
        })
      }),
      http.post('/api/v2/registry/model-plugins/plugin-rfd/validations', () => {
        validated = true
        return envelope({ operation_id: 'operation-validate-rfd', resource_id: 'plugin-rfd' })
      }),
      http.get('/api/v2/operations/operation-validate-rfd/events', () =>
        new HttpResponse(
          `event: operation\ndata: ${JSON.stringify({
            id: 'operation-validate-rfd', status: 'succeeded', kind: 'registry.model_plugin.validate',
          })}\n\n`,
          { headers: { 'Content-Type': 'text/event-stream' } },
        )),
    )

    renderWithProviders(<WorkflowPage />)

    fireEvent.click(await screen.findByRole('button', { name: 'Validate declaration' }))
    await waitFor(() => expect(validated).toBe(true))
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Validate declaration' })).not.toBeInTheDocument(),
    )
    expect(pluginRequests).toBeGreaterThan(1)
    expect(preflightRequests).toBeGreaterThan(1)
    expect(screen.getByText(/no current runtime proof/)).toBeInTheDocument()
  })

  it('Workflow does not offer registry validation to non-admin users', async () => {
    window.location.hash = '/workflow?project=proj_layer8'
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher', username: 'scientist' }))
    installBaseHandlers(readinessReady)
    const workflowRun = {
      id: 'run_layer8', project_id: 'proj_layer8', name: 'Plugin validation', status: 'draft',
      graph: { nodes: [], edges: [], layout: {} }, version: 1, created_by: 'user_test',
      created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
    }
    server.use(
      http.get('/api/v2/projects/proj_layer8/workflow-runs', () => envelope({ items: [workflowRun] })),
      http.get('/api/v2/workflow-runs/run_layer8/graph', () =>
        envelope({ workflow: workflowRun, nodes: [], edges: [], layout: {} })),
      http.get('/api/v2/registry/model-plugins', () => envelope({ items: [{
        id: 'plugin-rfd', plugin_key: 'RFdiffusion', plugin_version: '1.1.0', name: 'RFdiffusion',
        container_image: '/work/rfd', command: 'run', parameter_schema: {}, output_schema: {},
        enabled: true, validation_status: 'unknown', validated_at: null, validation_errors: [],
        version: 1, created_at: '', updated_at: '', input_ports: [], output_ports: [], resources: {},
        runtime_mode: 'conda', output_parser: null, input_adapter: null,
      }], next_cursor: null })),
      http.get('/api/v2/workflow-runs/run_layer8/preflight', () => envelope({
        stage: 'workflow', allowed: true, project_id: 'proj_layer8', workflow_run_id: 'run_layer8',
        node_run_id: null, blockers: [], warnings: [{
          code: 'plugin_unvalidated', message: "Plugin 'RFdiffusion' declaration status is 'unknown'",
          plugin_key: 'RFdiffusion',
        }], checks: {},
      })),
    )

    renderWithProviders(<WorkflowPage />)

    expect(await screen.findByText(/declaration status is 'unknown'/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Validate declaration' })).not.toBeInTheDocument()
  })

  it('Candidates exposes scoring provenance controls and empty-structure recovery for generated candidates', async () => {
    window.location.hash = '/candidates?project=proj_layer8'
    installBaseHandlers(readinessReady)
    server.use(
      http.get('/api/v2/projects/proj_layer8/candidate-funnel', () =>
        envelope({ generated: 1, designed: 1, folded: 0, scored: 0, ordered: 0 }),
      ),
      http.get('/api/v2/projects/proj_layer8/candidates', () =>
        envelope({
          items: [
            {
              id: 'binder_candidate_001',
              project_id: 'proj_layer8',
              candidate_key: 'binder_candidate_001',
              name: 'binder_candidate_001',
              status: 'generated',
              rank: null,
              score: 81,
              scores: { interface_score: 81, design_score: 81, plddt: 72, solubility_score: 0.77 },
              properties: { family: 'binder_design_route', pred_kd: 'Not scored', decision: 'Review', next_action: 'Run folding before ordering.' },
              structure_artifact_id: null,
              complex_artifact_id: null,
              source_job_id: null,
              version: 1,
              created_at: '2026-07-01T00:00:00Z',
              updated_at: '2026-07-01T00:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      ),
      http.get('/api/v2/registry', () =>
        envelope({
          items: [
            {
              compute_node_id: 'cpu_local',
              node_name: 'Local CPU',
              node_type: 'CPU',
              status: 'available',
            },
          ],
          next_cursor: null,
        }),
      ),
    )

    renderWithProviders(<CandidatesPage />)

    expect((await screen.findAllByText('binder_candidate_001')).length).toBeGreaterThan(0)
    expect(screen.getByText('No structure file for this candidate yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download selected' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Select page' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Download selected (1)' })).toBeEnabled(),
    )
  })

  it('Results keeps interpretation and delivery packaging gated on measured evidence', async () => {
    window.location.hash = '/results?project=proj_layer8'
    installBaseHandlers(readinessReady)
    server.use(
      http.get('/api/v2/projects/proj_layer8/experiment-results', () => envelope({ items: [], next_cursor: null })),
      http.get('/api/v2/projects/proj_layer8/result-summary', () => envelope({ project_id: 'proj_layer8',
        candidate_count: 0, experiment_result_count: 0, available_artifact_count: 0,
        tested_candidate_count: 0, passed_result_count: 0, failed_result_count: 0,
        unknown_result_count: 0, pass_rate: null, top_candidate_ids: [], best_result_id: null,
        best_result_value: null, best_result_unit: null })),
      http.get('/api/v2/projects/proj_layer8/delivery-packages', () => envelope({ items: [], next_cursor: null })),
    )

    renderWithProviders(<ResultsPage />)

    expect(await screen.findByText('No wet-lab readouts are recorded for this project yet. Upload experiment results or run a validation workflow to populate this view.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Prepare delivery package' })).toBeDisabled()
    expect(
      screen.getByText('No delivery package has been generated from verified project artifacts yet.'),
    ).toBeInTheDocument()
  })
})
