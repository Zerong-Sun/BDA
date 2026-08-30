import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NormalizedResearchWorkspace } from '../../lib/api/researchWorkspace'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ResearchWorkspacePanel } from './ResearchWorkspacePanel'
import type { ResearchTab } from './researchUi'

const getWorkspace = vi.hoisted(() => vi.fn())
let activeProjectId = 'project-one'

vi.mock('../../lib/api/researchWorkspace', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api/researchWorkspace')>()
  return { ...actual, getResearchWorkspace: getWorkspace }
})
vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    projectId: activeProjectId,
    activeProject: { id: activeProjectId, name: `Project ${activeProjectId}`, summary: 'Project summary' },
  }),
}))
vi.mock('./ProjectReviewPanel', () => ({ ProjectReviewPanel: () => <div>review operations</div> }))
vi.mock('./GenerateSimilarResearchPanel', () => ({
  GenerateSimilarResearchPanel: ({ defaultTopic }: { defaultTopic: string }) => (
    <div>generate operation · {defaultTopic}</div>
  ),
}))
vi.mock('./LiteraturePanel', () => ({ LiteraturePanel: () => <div>literature operations</div> }))
vi.mock('./TargetIntelligencePanel', () => ({ TargetIntelligencePanel: () => <div>target operations</div> }))
vi.mock('./KnowledgePanel', () => ({ KnowledgePanel: () => <div>knowledge operations</div> }))
vi.mock('../pdb-viewer/StructureViewerLazy', () => ({ StructureViewerLazy: () => <div>structure viewer</div> }))

const localized = (en: string, zh = `中文 ${en}`) => ({ en, zh, default: en })

function fixture(projectId = activeProjectId): NormalizedResearchWorkspace {
  return {
    project: {
      id: projectId,
      name: localized(`Workspace ${projectId}`),
      summary: localized(`Summary ${projectId}`),
      project_type: 'research',
      source_project_key: 'PD1',
      source_package_id: 'package-one',
      package: { version: '2.0', as_of: '2026-07-20' },
    },
    review_document: {
      id: 'review-one',
      title: localized('Unique review title'),
      content: localized('Unique review body'),
      status: 'active',
      version: 1,
      updated_at: '2026-07-20T00:00:00Z',
    },
    review_sections: [],
    graph_nodes: [{ id: 'node-one', kind: 'target', label: localized('Node one'), description: localized('Node description'), reference_ids: [], review_status: 'accepted' }],
    graph_edges: [{ id: 'edge-one', source: 'node-one', target: 'node-two', source_label: localized('Node one'), target_label: localized('Node two'), predicate: 'binds', summary: localized('Unique edge summary'), context: localized('Unique edge context'), assertion: 'established_fact', evidence_grade: 'A', reference_ids: ['REF-1'], source_urls: ['https://example.test/ref'], review_status: 'accepted' }],
    references: [{
      document_id: 'document-one',
      ref_id: 'REF-1',
      title: localized('Unique paper title'),
      authors: 'Ada Author; Ben Writer',
      doi: '10.1000/example',
      status: 'ready',
      verification_status: 'verified',
      url: 'https://example.test/ref',
    }],
    structures: [{ artifact_id: 'artifact-one', pdb_id: '1ABC', name: localized('Unique structure name'), role: localized('Template role'), method: localized('X-ray'), resolution: 2.1, status: 'available', download_url: 'https://example.test/1abc.cif' }],
    research_targets: [{ id: 'target-one', candidate_key: 'C01', name: localized('Unique target name'), pain_group: localized('Group one'), protein_type: localized('Protein'), localization: localized('Membrane'), axis: localized('Axis'), score: 91, rank: 1, scores: { evidence: 90 }, properties: { bibliometrics: { recent_5y_count: 12 } }, reference_ids: ['REF-1'] }],
    datasets: [{ id: 'dataset-one', key: 'identifiers', title: localized('Unique dataset title'), content: localized('Dataset'), data: [{ id: 'ID-1', value: 2 }], version: 1 }],
    methods: [{ id: 'method-one', key: 'methods', title: localized('Unique method title'), content: localized('Unique method body'), data: null, version: 1 }],
    counts: { references: 1 },
  }
}

describe('ResearchWorkspacePanel', () => {
  beforeEach(() => {
    activeProjectId = 'project-one'
    useAppStore.setState({ language: 'en' })
    getWorkspace.mockReset()
    getWorkspace.mockImplementation(async (projectId: string) => fixture(projectId))
  })

  afterEach(cleanup)

  it.each([
    ['evidence', 'edge-one'],
    ['references', 'Unique paper title'],
    ['structures', 'Unique structure name'],
    ['data', 'Unique dataset title'],
    ['methods', 'Unique method title'],
  ] satisfies Array<[ResearchTab, string]>)('renders %s from the backend workspace once', async (tab, stableText) => {
    renderWithProviders(<ResearchWorkspacePanel view={tab} />)
    await screen.findByText(stableText)
    expect(screen.getAllByText(stableText)).toHaveLength(1)
  })

  it('renders the project review inside relationship evidence', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    await screen.findByText('Unique review body')
    expect(screen.getAllByText('Unique review body')).toHaveLength(1)
  })

  it('renders the saved structure in the 3D viewer', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="structures" />)
    expect(await screen.findByText('structure viewer')).toBeInTheDocument()
  })

  it('renders authors and a clickable DOI link for references', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="references" />)
    expect(await screen.findByText('Ada Author; Ben Writer')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'DOI 10.1000/example' })).toHaveAttribute(
      'href',
      'https://doi.org/10.1000/example',
    )
  })

  it('switches research body language without fetching again', async () => {
    const rendered = renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    await screen.findByText('Unique review body')
    useAppStore.setState({ language: 'zh' })
    rendered.rerender(<ResearchWorkspacePanel view="evidence" />)
    expect(await screen.findByText('中文 Unique review body')).toBeInTheDocument()
    expect(getWorkspace).toHaveBeenCalledTimes(1)
  })

  it('keeps an English evidence-search topic when the interface is Chinese', async () => {
    useAppStore.setState({ language: 'zh' })
    renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    fireEvent.click(await screen.findByText('生成同类研究'))
    expect(await screen.findByText('generate operation · Workspace project-one')).toBeInTheDocument()
  })

  it('uses the bilingual display dataset instead of raw package values', async () => {
    const data = fixture()
    data.datasets[0].data = [{ definition: '原始中文定义' }]
    data.datasets[0].display_data = [{ definition: { zh: '中文定义', en: 'English definition' } }]
    getWorkspace.mockResolvedValueOnce(data)

    renderWithProviders(<ResearchWorkspacePanel view="data" />)
    expect(await screen.findByText('English definition')).toBeInTheDocument()
    expect(screen.queryByText('中文定义')).not.toBeInTheDocument()
  })

  it('silently preserves the original for single-language content', async () => {
    const data = fixture()
    data.review_document!.content = { en: 'English only body', default: 'English only body' }
    getWorkspace.mockResolvedValueOnce(data)
    useAppStore.setState({ language: 'zh' })
    renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    await screen.findByText('English only body')
    expect(screen.queryByText('该条目尚无当前语言译文，正在显示原文。')).not.toBeInTheDocument()
  })

  it('uses project-scoped workspace queries when the active project changes', async () => {
    const rendered = renderWithProviders(<ResearchWorkspacePanel view="references" />)
    await waitFor(() => expect(getWorkspace).toHaveBeenCalledWith('project-one'))
    activeProjectId = 'project-two'
    rendered.rerender(<ResearchWorkspacePanel view="references" />)
    await waitFor(() => expect(getWorkspace).toHaveBeenCalledWith('project-two'))
    expect(getWorkspace.mock.calls.map(([projectId]) => projectId)).toEqual(['project-one', 'project-two'])
  })

  it('renders loading while the aggregate request is pending', () => {
    getWorkspace.mockReturnValueOnce(new Promise(() => undefined))
    renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    expect(screen.getByText('Loading the project research workspace…')).toBeInTheDocument()
  })

  it('renders an error and retries the aggregate request', async () => {
    getWorkspace.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(fixture())
    renderWithProviders(<ResearchWorkspacePanel view="references" />)
    expect(await screen.findByText('The research workspace could not be loaded from the backend.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Unique paper title')).toBeInTheDocument()
    expect(getWorkspace).toHaveBeenCalledTimes(2)
  })

  it('renders the tab-specific empty state', async () => {
    const data = fixture()
    data.review_document = null
    data.review_sections = []
    data.graph_nodes = []
    data.graph_edges = []
    getWorkspace.mockResolvedValueOnce(data)
    renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    expect(await screen.findByText('No evidence relationships are available for this project.')).toBeInTheDocument()
  })

  it('keeps operation queries unmounted until their accordion is opened', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="references" />)

    const trigger = await screen.findByRole('button', {
      name: 'Literature ingestion and claim review',
    })
    expect(screen.queryByText('literature operations')).not.toBeInTheDocument()
    fireEvent.click(trigger)
    expect(await screen.findByText('literature operations')).toBeInTheDocument()
  })
})
