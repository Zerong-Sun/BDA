import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { HashRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createCampaign,
  evaluateCampaignRound,
  getCampaign,
  listProjectCampaigns,
  reviewCampaignDecision,
  updateCampaignDecision,
} from '../../lib/api/campaigns'
import {
  advanceTargetIntelligenceRun,
  analyzeTargetIntelligence,
  applyTargetDesignRoute,
  createLiteratureSubscription,
  detectLiteratureRelations,
  exportTargetDossier,
  getTargetIntelligenceRun,
  ingestLiterature,
  listLiteratureClaims,
  listLiteratureRelations,
  listLiteratureSearches,
  listLiteratureSubscriptions,
  reviewLiteratureClaim,
  reviewLiteratureRelation,
  reviewTargetEvidence,
  reviewTargetHotspot,
  runLiteratureSubscription,
  searchLiteratureLibrary,
  updateLiteratureSubscription,
} from '../../lib/api/copilot'
import { confirmTargetIdentity, getProjectResearchSummary } from '../../lib/api/projects'
import { fetchPdb } from '../../lib/api/targets'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useProjectTargetStructure } from '../../lib/hooks/useProjectTargetStructure'
import { useAppStore } from '../../lib/store/appStore'
import { CampaignPanel } from './CampaignPanel'
import { LiteraturePanel } from './LiteraturePanel'
import { TargetIntelligencePanel } from './TargetIntelligencePanel'

vi.mock('../../lib/api/campaigns')
vi.mock('../../lib/api/copilot')
vi.mock('../../lib/api/projects', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../lib/api/projects')>()
  return { ...original, getProjectResearchSummary: vi.fn(), confirmTargetIdentity: vi.fn() }
})
vi.mock('../../lib/api/targets', () => ({ fetchPdb: vi.fn() }))
vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: vi.fn() }))
vi.mock('../../lib/hooks/useProjectTargetStructure', () => ({ useProjectTargetStructure: vi.fn() }))
vi.mock('../pdb-viewer/StructureViewerLazy', () => ({
  StructureViewerLazy: () => <div aria-label="structure viewer" />,
}))

const PROJECT_ID = 'project-one'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}

function renderPanel(panel: ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const rendered = render(
    <QueryClientProvider client={client}>
      <HashRouter>{panel}</HashRouter>
    </QueryClientProvider>,
  )
  return { ...rendered, client }
}

const targetReport = {
  run_id: 'target-run-one',
  stage: 'evidence_review',
  target: {
    name: 'PD-1',
    organism: 'Homo sapiens',
    uniprot_accession: 'Q15116',
    confidence: 'curated',
    construct_recommendation: 'Use the extracellular domain.',
  },
  evidence: [{
    source_type: 'pdb',
    identifier: '5IUS',
    title: 'PD-1 complex',
    claim: 'The extracellular domain forms the ligand interface.',
    claim_type: 'structure',
    evidence_level: 'A',
    confidence: 'high',
    review_status: 'pending_review',
    metadata: { evidence_item_id: 'evidence-one' },
    url: 'https://www.rcsb.org/structure/5IUS',
  }],
  hotspots: [],
  design_routes: [{
    route_id: 'route-one',
    label: 'Interface binder',
    fit: 'high',
    rank: 1,
    methods: ['ProteinMPNN'],
    rationale: 'Targets the ligand interface.',
    risks: [],
    module_ids: ['proteinmpnn'],
    status: 'proposed',
  }],
  experiment_plan: {
    binding_validation: ['SPR'],
    specificity: [],
    developability: [],
    mutation_or_epitope_validation: [],
  },
  audit: {
    agent_roles: ['evidence'],
    agent_steps: [{
      role: 'evidence',
      stage: 'collecting_evidence',
      status: 'completed',
      summary: 'Collected structural evidence.',
    }],
    source_status: {
      pdb: { source_type: 'pdb', status: 'ok', item_count: 1 },
    },
    limitations: ['Human review is required.'],
  },
} as const

function mockTargetReport(report: unknown) {
  vi.mocked(analyzeTargetIntelligence).mockResolvedValue(report as never)
  vi.mocked(getTargetIntelligenceRun).mockResolvedValue({
    run: {
      run_id: 'target-run-one',
      project_id: PROJECT_ID,
      target_query: 'PD-1',
      objective: 'Block ligand binding',
      modality: 'binder',
      status: 'running',
      created_at: '2026-07-29T00:00:00Z',
      updated_at: '2026-07-29T00:00:00Z',
    },
    report,
  } as never)
}

async function analyzeTarget() {
  fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'PD-1' } })
  fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Block ligand binding' } })
  fireEvent.click(screen.getByRole('button', { name: 'Analyze target' }))
  expect(await screen.findByText('PD-1 complex')).toBeInTheDocument()
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.setItem('bda_user', JSON.stringify({ role: 'admin' }))
  useAppStore.setState({ language: 'en', activeProjectId: PROJECT_ID })
  vi.mocked(useProjectContext).mockReturnValue({
    projectId: PROJECT_ID,
    activeProject: { id: PROJECT_ID, name: 'PD-1 program', status: 'active' },
  } as ReturnType<typeof useProjectContext>)
  vi.mocked(useProjectTargetStructure).mockReturnValue({
    data: null,
  } as ReturnType<typeof useProjectTargetStructure>)
  vi.mocked(getProjectResearchSummary).mockResolvedValue({
    brief: { scope: { source_material: [] } },
  } as never)
  vi.mocked(listLiteratureClaims).mockResolvedValue({ items: [], next_cursor: null } as never)
  vi.mocked(listLiteratureRelations).mockResolvedValue({ items: [], next_cursor: null } as never)
  vi.mocked(listLiteratureSubscriptions).mockResolvedValue({ items: [], next_cursor: null } as never)
  vi.mocked(listLiteratureSearches).mockResolvedValue({ items: [], next_cursor: null } as never)
  vi.mocked(searchLiteratureLibrary).mockResolvedValue({ items: [], next_cursor: null } as never)
  vi.mocked(ingestLiterature).mockResolvedValue({} as never)
  vi.mocked(createLiteratureSubscription).mockResolvedValue({} as never)
  vi.mocked(detectLiteratureRelations).mockResolvedValue({} as never)
  vi.mocked(reviewLiteratureClaim).mockResolvedValue({} as never)
  vi.mocked(reviewLiteratureRelation).mockResolvedValue({} as never)
  vi.mocked(runLiteratureSubscription).mockResolvedValue({} as never)
  vi.mocked(updateLiteratureSubscription).mockResolvedValue({} as never)
  mockTargetReport(targetReport)
  vi.mocked(advanceTargetIntelligenceRun).mockResolvedValue(targetReport as never)
  vi.mocked(reviewTargetEvidence).mockResolvedValue(targetReport as never)
  vi.mocked(reviewTargetHotspot).mockResolvedValue(targetReport as never)
  vi.mocked(applyTargetDesignRoute).mockResolvedValue({} as never)
  vi.mocked(exportTargetDossier).mockResolvedValue({
    run_id: 'target-run-one',
    export_format: 'json',
    filename: 'target.json',
    media_type: 'application/json',
    content: '{}',
  })
  vi.mocked(confirmTargetIdentity).mockResolvedValue({} as never)
  vi.mocked(fetchPdb).mockResolvedValue({} as never)
  vi.mocked(listProjectCampaigns).mockResolvedValue({
    items: [{
      id: 'campaign-one',
      project_id: PROJECT_ID,
      name: 'Affinity campaign',
      objective: 'Improve affinity',
      status: 'active',
      config: { max_rounds: 3 },
    }],
    next_cursor: null,
  } as never)
  vi.mocked(getCampaign).mockResolvedValue({
    id: 'campaign-one',
    project_id: PROJECT_ID,
    name: 'Affinity campaign',
    objective: 'Improve affinity',
    status: 'active',
    config: { max_rounds: 3 },
    rounds: [{
      id: 'round-one',
      campaign_id: 'campaign-one',
      round_number: 1,
      status: 'ready_for_evaluation',
      workflow_run_id: 'workflow-one',
      evaluations: [],
      decisions: [{
        id: 'decision-one',
        round_id: 'round-one',
        review_status: 'pending',
        parameter_patch: { models: { temperature: 0.2 } },
      }],
    }],
  } as never)
  vi.mocked(createCampaign).mockResolvedValue({ id: 'campaign-two' } as never)
  vi.mocked(evaluateCampaignRound).mockResolvedValue({} as never)
  vi.mocked(reviewCampaignDecision).mockResolvedValue({} as never)
  vi.mocked(updateCampaignDecision).mockResolvedValue({} as never)
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
})

describe('LiteraturePanel', () => {
  it('keeps role gates, polling, and registry controls together', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    const { client } = renderPanel(<LiteraturePanel />)

    const ingestButton = await screen.findByRole('button', { name: 'Ingest now' })
    expect(ingestButton).toBeDisabled()
    expect(ingestButton).toHaveAttribute('data-slot', 'button')
    expect(screen.getByPlaceholderText('Search literature for this project')).toHaveAttribute(
      'data-slot',
      'input',
    )
    expect(screen.getByRole('button', { name: 'Detect relationships' })).toBeDisabled()

    const pollingQuery = client.getQueryCache().find({
      queryKey: ['literature-search-runs', PROJECT_ID],
    })
    const pollingOptions = pollingQuery?.options as { refetchInterval?: unknown }
    expect(pollingOptions.refetchInterval).toBeTypeOf('function')
    const refetchInterval = pollingOptions.refetchInterval as (query: {
      state: { data: { items: Array<{ status: string }> } }
    }) => number | false
    expect(refetchInterval({ state: { data: { items: [{ status: 'running' }] } } })).toBe(2000)
    expect(refetchInterval({ state: { data: { items: [{ status: 'completed' }] } } })).toBe(false)
  })

  it('invalidates every dependent literature view after ingestion', async () => {
    const { client } = renderPanel(<LiteraturePanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    fireEvent.click(await screen.findByRole('button', { name: 'Ingest now' }))

    await waitFor(() => expect(ingestLiterature).toHaveBeenCalledWith(PROJECT_ID, expect.any(String)))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['literature-search-runs', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['literature-claims', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
  })

  it('derives Timeline completion from the visible ordered run slice', async () => {
    const chronologicalRuns = Array.from({ length: 12 }, (_, index) => ({
      id: `run-${String(index).padStart(2, '0')}`,
      project_id: PROJECT_ID,
      query: `query-${index}`,
      sources: ['europe_pmc'],
      status: index === 11 ? 'running' : 'completed',
      requested_limit: 5,
      result_count: 5,
      fetch_full_text: true,
      extract_claims: true,
      created_at: `2026-07-29T00:${String(index === 10 ? 9 : index).padStart(2, '0')}:00Z`,
    }))
    const shuffledRuns = [11, 0, 6, 3, 10, 1, 8, 4, 9, 2, 7, 5].map(
      (index) => chronologicalRuns[index],
    )
    vi.mocked(listLiteratureSearches).mockResolvedValue({
      items: shuffledRuns,
      next_cursor: null,
    } as never)

    renderPanel(<LiteraturePanel />)

    const newestRun = await screen.findByText('Europe PMC · query-11')
    const visibleItems = screen.getAllByText(/Europe PMC · query-/)
    expect(visibleItems).toHaveLength(10)
    expect(visibleItems.map((item) => item.textContent)).toEqual([
      'Europe PMC · query-2',
      'Europe PMC · query-3',
      'Europe PMC · query-4',
      'Europe PMC · query-5',
      'Europe PMC · query-6',
      'Europe PMC · query-7',
      'Europe PMC · query-8',
      'Europe PMC · query-9',
      'Europe PMC · query-10',
      'Europe PMC · query-11',
    ])
    expect(screen.getByText('Europe PMC · query-10').closest('[data-slot="timeline-item"]')).toHaveAttribute('data-completed')
    expect(newestRun.closest('[data-slot="timeline-item"]')).not.toHaveAttribute('data-completed')
  })

  it('invalidates subscription and relation views after their mutations', async () => {
    vi.mocked(listLiteratureSubscriptions).mockResolvedValue({
      items: [{
        subscription_id: 'subscription-one',
        name: 'PD-1 surveillance',
        query: 'PD-1',
        enabled: true,
        interval_hours: 24,
        result_limit: 5,
        fetch_full_text: true,
        extract_claims: true,
        next_run_at: '2026-07-30T00:00:00Z',
      }],
      next_cursor: null,
    } as never)
    vi.mocked(listLiteratureClaims).mockResolvedValue({
      items: [
        { id: 'claim-one', claim: 'PD-1 binds PD-L1.', confidence: 'high', review_status: 'accepted', attributes: {} },
        { id: 'claim-two', claim: 'PD-1 inhibits signaling.', confidence: 'high', review_status: 'accepted', attributes: {} },
      ],
      next_cursor: null,
    } as never)
    vi.mocked(listLiteratureRelations).mockResolvedValue({
      items: [{
        id: 'relation-one',
        source_claim_id: 'claim-one',
        target_claim_id: 'claim-two',
        relation_type: 'supports',
        rationale: 'Shared pathway evidence.',
        review_status: 'pending_review',
      }],
      next_cursor: null,
    } as never)
    const { client } = renderPanel(<LiteraturePanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    fireEvent.click(await screen.findByRole('button', { name: 'Pause' }))
    await waitFor(() => expect(updateLiteratureSubscription).toHaveBeenCalled())
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['literature-subscriptions', PROJECT_ID],
    }))
    expect(invalidate).toHaveBeenCalledTimes(1)
    invalidate.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Run now' }))
    await waitFor(() => expect(vi.mocked(runLiteratureSubscription).mock.calls[0]?.[0])
      .toBe('subscription-one'))
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['literature-subscriptions', PROJECT_ID],
    }))
    expect(invalidate).toHaveBeenCalledTimes(1)
    invalidate.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Detect relationships' }))
    await waitFor(() => expect(detectLiteratureRelations).toHaveBeenCalledWith(PROJECT_ID))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['literature-relations', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
    expect(invalidate).toHaveBeenCalledTimes(2)
    invalidate.mockClear()

    const relation = screen.getByText('Shared pathway evidence.').closest('[data-slot="frame-panel"]')
    fireEvent.click(within(relation as HTMLElement).getByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(reviewLiteratureRelation).toHaveBeenCalledWith('relation-one', 'accepted'))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['literature-relations', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
    expect(invalidate).toHaveBeenCalledTimes(2)
  })
})

describe('TargetIntelligencePanel', () => {
  it('uses registry form controls and preserves evidence review and route gates', async () => {
    const reviewPending = deferred<never>()
    vi.mocked(reviewTargetEvidence).mockReturnValue(reviewPending.promise)
    renderPanel(<TargetIntelligencePanel />)

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'PD-1' } })
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Block ligand binding' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze target' }))

    expect(await screen.findByText('PD-1 complex')).toBeInTheDocument()
    expect(screen.getByLabelText('Target')).toHaveAttribute('data-slot', 'input')
    expect(screen.getByLabelText('Objective')).toHaveAttribute('data-slot', 'textarea')
    expect(screen.getByLabelText('Modality')).toHaveAttribute('data-slot', 'select-trigger')
    expect(screen.getByRole('button', { name: 'Advance' })).toBeDisabled()

    const route = screen.getByRole('button', { name: /Interface binder/ })
    expect(route).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Download export' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(reviewTargetEvidence).toHaveBeenCalledWith(
      'target-run-one',
      'evidence-one',
      'accepted',
    ))
    expect(screen.getByRole('button', { name: 'Accept' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
  })

  it('owns right-side overflow for all three target dashboard bands', () => {
    renderPanel(<TargetIntelligencePanel />)

    const detail = screen.getByTestId('target-intelligence-detail')
    expect(detail).toHaveClass('lg:overflow-y-auto')
    expect(detail.className).not.toContain('lg:grid-rows-[minmax(0,1fr)_minmax(20rem,0.9fr)]')
  })

  it('invalidates the run and workspace after an evidence review', async () => {
    const { client } = renderPanel(<TargetIntelligencePanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'PD-1' } })
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Block ligand binding' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze target' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Accept' }))

    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['target-intelligence-run', 'target-run-one'] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
  })

  it('preserves identity confirmation, structure fetch, export, and download effects', async () => {
    const createObjectUrl = vi.fn(() => 'blob:target-dossier')
    const revokeObjectUrl = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectUrl })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectUrl })
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const { client } = renderPanel(<TargetIntelligencePanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await analyzeTarget()
    invalidate.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Confirm this target identity' }))
    await waitFor(() => expect(confirmTargetIdentity).toHaveBeenCalledWith(PROJECT_ID, expect.objectContaining({
      target_name: 'PD-1',
      uniprot_accession: 'Q15116',
    })))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['target-readiness', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['project-target-structure', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['project-overview', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
    expect(invalidate).toHaveBeenCalledTimes(4)
    invalidate.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Fetch and store structure' }))
    await waitFor(() => expect(fetchPdb).toHaveBeenCalledWith('5IUS', PROJECT_ID))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['project-target-structure', PROJECT_ID] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
    expect(invalidate).toHaveBeenCalledTimes(2)

    fireEvent.click(screen.getByRole('button', { name: 'JSON' }))
    await waitFor(() => expect(exportTargetDossier).toHaveBeenCalledWith('target-run-one', 'json'))
    const download = screen.getByRole('button', { name: 'Download export' })
    await waitFor(() => expect(download).toBeEnabled())
    fireEvent.click(download)
    expect(createObjectUrl).toHaveBeenCalledWith(expect.any(Blob))
    expect(anchorClick).toHaveBeenCalled()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:target-dossier')
  })

  it('preserves advance and hotspot review invalidations', async () => {
    const acceptedReport = {
      ...targetReport,
      evidence: [{ ...targetReport.evidence[0], review_status: 'accepted' }],
    }
    mockTargetReport(acceptedReport)
    const { client } = renderPanel(<TargetIntelligencePanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await analyzeTarget()

    fireEvent.click(screen.getByRole('button', { name: 'Advance' }))
    await waitFor(() => expect(advanceTargetIntelligenceRun).toHaveBeenCalledWith('target-run-one'))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['target-intelligence-run', 'target-run-one'] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })

    cleanup()
    const hotspotReport = {
      ...targetReport,
      stage: 'hotspot_review',
      evidence: [{ ...targetReport.evidence[0], review_status: 'accepted' }],
      hotspots: [{
        residue: 'Y68',
        region: 'interface',
        status: 'pending_review',
        rationale: 'Interface contact.',
        extraction_method: 'structure',
        metadata: { hotspot_id: 'hotspot-one' },
      }],
    }
    mockTargetReport(hotspotReport)
    const hotspotRendered = renderPanel(<TargetIntelligencePanel />)
    const hotspotInvalidate = vi.spyOn(hotspotRendered.client, 'invalidateQueries')
    await analyzeTarget()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(reviewTargetHotspot).toHaveBeenCalledWith(
      'target-run-one',
      'hotspot-one',
      { status: 'confirmed' },
    ))
    await waitFor(() => {
      expect(hotspotInvalidate).toHaveBeenCalledWith({ queryKey: ['target-intelligence-run', 'target-run-one'] })
      expect(hotspotInvalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
  })

  it('preserves completed-route application and dependent invalidations', async () => {
    const completedReport = { ...targetReport, stage: 'completed' }
    mockTargetReport(completedReport)
    vi.mocked(applyTargetDesignRoute).mockResolvedValue({
      workflow_run: { id: 'workflow-two' },
      module_selection_note: 'Selected route modules.',
      parameter_lineage: [],
      next_actions: [],
    } as never)
    const { client } = renderPanel(<TargetIntelligencePanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await analyzeTarget()

    fireEvent.click(screen.getByRole('button', { name: 'Create workflow' }))
    await waitFor(() => expect(applyTargetDesignRoute).toHaveBeenCalledWith('target-run-one', {
      route_id: 'route-one',
      selected_module_ids: ['proteinmpnn'],
    }))
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['target-intelligence-run', 'target-run-one'] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research-workspace', PROJECT_ID] })
    })
  })
})

describe('CampaignPanel', () => {
  it('keeps five-second detail polling and freezes review and patch actions together', async () => {
    const reviewPending = deferred<never>()
    vi.mocked(reviewCampaignDecision).mockReturnValue(reviewPending.promise)
    const { client } = renderPanel(<CampaignPanel />)

    fireEvent.click(await screen.findByRole('button', { name: /Affinity campaign/ }))
    expect(await screen.findByRole('textbox', { name: 'Round 1 parameter patch' })).toBeInTheDocument()

    const detailQuery = client.getQueryCache().find({ queryKey: ['campaign', 'campaign-one'] })
    const detailOptions = detailQuery?.options as { refetchInterval?: unknown }
    expect(detailOptions.refetchInterval).toBe(5000)
    expect(screen.getByTestId('campaign-rounds')).toHaveAttribute('data-slot', 'timeline')

    fireEvent.click(screen.getByRole('button', { name: 'Approve and create next round' }))
    await waitFor(() => expect(reviewCampaignDecision).toHaveBeenCalledWith('decision-one', true))

    expect(screen.getByRole('button', { name: 'Save patch' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Approve and create next round' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Evaluate round' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Create closed-loop campaign' })).toBeDisabled()
  })

  it('locks decision review while evaluation or campaign creation is pending', async () => {
    const evaluationPending = deferred<never>()
    vi.mocked(evaluateCampaignRound).mockReturnValue(evaluationPending.promise)
    const { unmount } = renderPanel(<CampaignPanel />)

    fireEvent.click(await screen.findByRole('button', { name: /Affinity campaign/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Evaluate round' }))
    await waitFor(() => expect(evaluateCampaignRound).toHaveBeenCalledWith('campaign-one', 1))
    expect(screen.getByRole('button', { name: 'Create closed-loop campaign' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save patch' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Approve and create next round' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()

    unmount()
    const creationPending = deferred<never>()
    vi.mocked(createCampaign).mockReturnValue(creationPending.promise)
    renderPanel(<CampaignPanel />)
    fireEvent.click(await screen.findByRole('button', { name: /Affinity campaign/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Create closed-loop campaign' }))
    await waitFor(() => expect(createCampaign).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: 'Save patch' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Approve and create next round' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
  })

  it('invalidates the selected campaign after decision review', async () => {
    const { client } = renderPanel(<CampaignPanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    fireEvent.click(await screen.findByRole('button', { name: /Affinity campaign/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Approve and create next round' }))

    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['campaign', 'campaign-one'] })
    })
  })

  it('preserves patch save, round evaluation, and rejection effects', async () => {
    const { client } = renderPanel(<CampaignPanel />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    fireEvent.click(await screen.findByRole('button', { name: /Affinity campaign/ }))
    const patch = await screen.findByRole('textbox', { name: 'Round 1 parameter patch' })

    fireEvent.change(patch, { target: { value: '{"models":{"temperature":0.4}}' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save patch' }))
    await waitFor(() => expect(updateCampaignDecision).toHaveBeenCalledWith(
      'decision-one',
      { models: { temperature: 0.4 } },
      'Reviewed in Research workspace.',
    ))
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['campaign', 'campaign-one'],
    }))
    expect(invalidate).toHaveBeenCalledTimes(1)
    invalidate.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Evaluate round' }))
    await waitFor(() => expect(evaluateCampaignRound).toHaveBeenCalledWith('campaign-one', 1))
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['campaign', 'campaign-one'],
    }))
    expect(invalidate).toHaveBeenCalledTimes(1)
    invalidate.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    await waitFor(() => expect(reviewCampaignDecision).toHaveBeenCalledWith('decision-one', false))
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['campaign', 'campaign-one'],
    }))
    expect(invalidate).toHaveBeenCalledTimes(1)
  })
})
