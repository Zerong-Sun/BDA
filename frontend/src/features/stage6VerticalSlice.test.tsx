import { fireEvent, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ApiState } from '../components/ui/ApiState'
import { Topbar } from '../components/ui/Topbar'
import { WorkflowProgress } from './experiments/WorkflowProgress'
import { CandidateStructureOverlay } from './candidates/CandidateStructureOverlay'
import { TargetStructureOverlay } from './experiments/TargetStructureOverlay'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import type { ProjectOverview } from '../lib/api/projects'
import type { Candidate } from '../lib/schemas/candidate'
import type { ProjectTargetStructure, TargetReadiness } from '../lib/schemas/target'

const blockedOverview: ProjectOverview = {
  project: {
    id: 'proj_vertical',
    organization_id: 'org_test',
    owner_id: 'user_test',
    name: 'Vertical slice',
    project_type: 'binder_design',
    status: 'active',
    summary: null,
    prompt: null,
    primary_target_id: null,
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
  funnel: { generated: 6, designed: 6, folded: 6, scored: 4, ordered: 1 },
  candidate_count: 6,
  experiment_result_count: 1,
  available_artifact_count: 2,
  active_job_count: 0,
  latest_workflow_id: 'run_vertical',
  next_action: 'Confirm target identity',
  target_readiness: {
    stage: 'identity_confirmation',
    ready_for_workflow: false,
    blockers: ['target_identity_confirmation_required'],
    next_action: 'Confirm target identity',
    target_id: null, structure_artifact_id: null, identity_status: null, structure_status: null,
  },
}

const candidate: Candidate = {
  id: 'cand_vertical', project_id: 'proj_vertical', candidate_key: 'cand_vertical', name: 'rf_route',
  status: 'folded', rank: 1, score: 93,
  scores: { interface_score: 93, design_score: 93, pred_kd: '0.8 nM', plddt: 90, interface_pae: 3.8, rosetta_score: -22, solubility_score: 0.8 },
  properties: { decision: 'Review', next_action: 'Review structure overlay and metric provenance.', chains: ['A', 'B'] },
  structure_artifact_id: 'artifact_structure', complex_artifact_id: 'artifact_complex', source_job_id: 'job_1',
  version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
}

const target: ProjectTargetStructure = {
  target: { id: 'target_vertical', project_id: 'proj_vertical', name: 'Vertical target', sequence: null,
    uniprot_accession: null, organism: null, identity_status: 'confirmed',
    structure_artifact_id: 'artifact_vertical', structure_status: 'approved', version: 1,
    target_kind: 'protein' as const, chemical_identity: {},
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z' },
  structure: { target_id: 'target_vertical', structure_status: 'approved', current_artifact_id: 'artifact_vertical',
    approved_revision_id: null, latest_revision: null },
  artifact: { id: 'artifact_vertical', project_id: 'proj_vertical', artifact_type: 'target_structure',
    filename: 'targets-prepared.pdb', content_type: 'chemical/x-pdb', status: 'available', size_bytes: 2500,
    checksum_sha256: 'b'.repeat(64), lineage: { pdb_id: '2XYZ', atom_count: 2500, chains: ['A', 'B'] },
    version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
    download_url: '/api/v2/artifacts/artifact_vertical/content' },
}

const readiness: TargetReadiness = {
  stage: 'identity_confirmation',
  ready_for_workflow: false,
  blockers: ['target_identity_confirmation_required'],
  next_action: 'Confirm target identity',
  target_id: 'target_vertical', structure_artifact_id: 'artifact_vertical',
  identity_status: 'confirmed', structure_status: 'approved',
}

beforeEach(() => {
  // Entered through the /experiments alias on purpose: passing here is the
  // redirect to /projects working end to end.
  window.location.hash = '/experiments?project=proj_vertical'
  useAppStore.setState({
    activeProjectId: 'proj_vertical',
    language: 'en',
  })
  server.use(
    http.get('/api/v2/projects', () =>
      HttpResponse.json({
        data: {
          items: [
            {
              project_id: 'proj_vertical',
              name: 'Vertical slice',
              project_type: 'binder_design',
              status: 'active',
              owner_id: 'user_test',
              summary: 'Stage 6 vertical slice',
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        },
        trace_id: 'test',
      }),
    ),
  )
})

describe('Stage 6 vertical slice', () => {
  it('keeps a non-expert on the readiness recovery path and explains candidate provenance', () => {
    renderWithProviders(
      <>
        <Topbar />
        <WorkflowProgress projectQuery="?project=proj_vertical" overview={blockedOverview} hasProject />
        <TargetStructureOverlay target={target} readiness={readiness} projectId="proj_vertical" />
        <CandidateStructureOverlay
          candidate={candidate}
          projectId="proj_vertical"
          structureMode="complex"
          metadata={{
            chains: ['A', 'B'],
            atom_count: 1400,
            chain_count: 2,
            residue_count: 280,
            ligands: [],
            format: 'pdb',
          }}
        />
      </>,
    )

    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '#/research?project=proj_vertical',
    )
    expect(screen.getByText('Target structure interpretation overlay')).toBeInTheDocument()
    expect(screen.getByText('Confirm target identity')).toBeInTheDocument()
    expect(screen.getByText('Candidate / binder chain (inferred)')).toBeInTheDocument()
    expect(screen.getByText('Target / partner chain (inferred)')).toBeInTheDocument()
    expect(screen.getAllByText(/No computed residue-contact table is attached/i)).toHaveLength(2)
    expect(screen.getByText('Candidate ranking record')).toBeInTheDocument()
  })

  it('offers a retry path for expected API failures', () => {
    const retry = vi.fn()

    renderWithProviders(
      <ApiState isError error={new Error('structure_not_available')} onRetry={retry}>
        <div>Loaded</div>
      </ApiState>,
    )

    expect(screen.getByText('structure_not_available')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(retry).toHaveBeenCalledTimes(1)
  })
})
