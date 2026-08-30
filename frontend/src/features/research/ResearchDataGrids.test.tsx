import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NormalizedResearchWorkspace } from '../../lib/api/researchWorkspace'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ResearchWorkspacePanel } from './ResearchWorkspacePanel'

const getWorkspace = vi.hoisted(() => vi.fn())

vi.mock('../../lib/api/researchWorkspace', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api/researchWorkspace')>()
  return { ...actual, getResearchWorkspace: getWorkspace }
})

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    projectId: 'project-grid',
    activeProject: { id: 'project-grid', name: 'Grid project', summary: 'Grid summary' },
  }),
}))

vi.mock('./ProjectReviewPanel', () => ({ ProjectReviewPanel: () => null }))
vi.mock('./GenerateSimilarResearchPanel', () => ({ GenerateSimilarResearchPanel: () => null }))
vi.mock('./LiteraturePanel', () => ({ LiteraturePanel: () => null }))
vi.mock('./TargetIntelligencePanel', () => ({ TargetIntelligencePanel: () => null }))
vi.mock('./KnowledgePanel', () => ({ KnowledgePanel: () => null }))
vi.mock('../pdb-viewer/StructureViewerLazy', () => ({ StructureViewerLazy: () => null }))

const localized = (en: string, zh = `中文 ${en}`) => ({ en, zh, default: en })

function workspaceFixture(): NormalizedResearchWorkspace {
  return {
    project: {
      id: 'project-grid',
      name: localized('Grid workspace'),
      summary: localized('Grid summary'),
      project_type: 'research',
      source_project_key: 'GRID',
      source_package_id: 'package-grid',
      package: { version: '1.0', as_of: '2026-07-29' },
    },
    review_document: null,
    review_sections: [],
    graph_nodes: [],
    graph_edges: [],
    references: [],
    structures: [],
    research_targets: [{
      id: 'target-stable',
      candidate_key: 'C-01',
      name: localized('Stable target'),
      pain_group: localized('Pain group'),
      protein_type: localized('Protein'),
      localization: localized('Membrane'),
      axis: localized('Axis'),
      score: 91,
      rank: 1,
      scores: {
        evidence: 90,
        novelty: 80,
        tractability: 70,
        human: 60,
        specificity: 50,
        safety: 40,
      },
      properties: { bibliometrics: { historical_count: 23, recent_5y_count: 8 } },
      reference_ids: ['REF-1'],
    }],
    datasets: [{
      id: 'dataset-stable',
      key: 'dot-keys',
      title: localized('Dot key dataset'),
      content: localized('Dataset'),
      data: [{
        'protein.name': 'raw package value',
        'protein-name': 'raw collision-looking value',
        score: 1,
      }],
      display_data: [{
        'protein.name': localized('Visible dotted protein', '可见点号蛋白'),
        'protein-name': localized('Visible dashed protein', '可见连字符蛋白'),
        score: 1,
      }],
      version: 1,
    }],
    methods: [],
    counts: {},
  }
}

describe('research data grids', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    getWorkspace.mockReset()
    getWorkspace.mockResolvedValue(workspaceFixture())
  })

  afterEach(cleanup)

  it('renders target and arbitrary-key dataset rows through ReUI data grids with stable ids', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="data" />)

    const tables = await screen.findAllByRole('table')
    expect(tables).toHaveLength(2)
    for (const table of tables) {
      expect(table).toHaveAttribute('data-slot', 'data-grid-table')
    }
    expect(document.querySelector('[data-row-id="target-stable"]')).toBeInTheDocument()
    expect(document.querySelector('[data-row-id="dataset-stable:0"]')).toBeInTheDocument()
    expect(screen.getByText('Visible dotted protein')).toBeInTheDocument()
    expect(screen.getByText('Visible dashed protein')).toBeInTheDocument()
    const datasetTable = tables[1]
    const sizingVariables = datasetTable.getAttribute('style') ?? ''
    expect(sizingVariables).toContain(
      '--col-dataset_70_72_6f_74_65_69_6e_2e_6e_61_6d_65-size',
    )
    expect(sizingVariables).toContain(
      '--col-dataset_70_72_6f_74_65_69_6e_2d_6e_61_6d_65-size',
    )
    expect(sizingVariables).not.toContain('--col-protein.name-size')
    expect(new Set(sizingVariables.match(/--col-dataset_[a-z0-9_]+-size/g)).size).toBe(3)
  })

  it('keeps dataset substring search separate from the structured evidence filters', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="data" />)

    const search = await screen.findByRole('textbox', { name: /search dataset/i })
    fireEvent.change(search, { target: { value: 'no matching protein' } })
    expect(screen.queryByText('Visible dotted protein')).not.toBeInTheDocument()
    expect(screen.queryByText('Visible dashed protein')).not.toBeInTheDocument()
    expect(screen.getByText('This dataset contains no rows.')).toBeInTheDocument()

    cleanup()
    renderWithProviders(<ResearchWorkspacePanel view="evidence" />)
    expect(await screen.findByTestId('research-assertion-filters')).toHaveAttribute(
      'data-slot',
      'filters',
    )
    expect(screen.getByRole('textbox', { name: 'Search subject, relation, object, or context' })).toHaveAttribute(
      'data-slot',
      'input',
    )
  })

  it('retains every scientific target column and its Copilot action', async () => {
    renderWithProviders(<ResearchWorkspacePanel view="data" />)

    const targetTable = (await screen.findAllByRole('table'))[0]
    expect(within(targetTable).getAllByRole('columnheader')).toHaveLength(11)
    expect(within(targetTable).getByRole('button', { name: /Ask Copilot about Stable target/i }))
      .toBeInTheDocument()
  })
})
