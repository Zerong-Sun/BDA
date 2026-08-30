import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { NormalizedResearchWorkspace } from '../../lib/api/researchWorkspace'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ProjectReviewPanel } from './ProjectReviewPanel'

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    projectId: 'project-one',
    activeProject: { id: 'project-one', name: 'Project one', summary: 'Summary' },
  }),
}))
vi.mock('../../lib/api/projects', () => ({
  upsertProjectResearchFinding: vi.fn(),
}))

const localized = (value: string) => ({ default: value, en: value })

const workspace: NormalizedResearchWorkspace = {
  project: {
    id: 'project-one',
    name: localized('Project one'),
    summary: localized('Summary'),
    project_type: 'research',
  },
  review_document: null,
  review_sections: [{
    track: 'prior_art_landscape',
    items: [{
      id: 'finding-one',
      finding_type: 'prior_art_landscape',
      title: localized('Migrated finding'),
      content: localized('A source-backed finding.'),
      evidence: {
        sources: ['PMID:12345678'],
        source_refs: ['PMID:12345678', 'DOI:10.1000/example'],
      },
      version: 1,
      created_at: '2026-07-26T00:00:00Z',
      updated_at: '2026-07-26T00:00:00Z',
    }],
  }],
  graph_nodes: [],
  graph_edges: [],
  references: [],
  structures: [],
  research_targets: [],
  methods: [],
  datasets: [],
  counts: {},
}

describe('ProjectReviewPanel', () => {
  afterEach(cleanup)

  it('renders migrated sources and newer source_refs on the finding card', async () => {
    renderWithProviders(<ProjectReviewPanel workspace={workspace} showDocument={false} />)

    expect(await screen.findByTestId('research-finding')).toHaveAttribute('data-finding-id', 'finding-one')
    expect(screen.getByRole('link', { name: 'PMID 12345678' })).toHaveAttribute(
      'href',
      'https://pubmed.ncbi.nlm.nih.gov/12345678/',
    )
    expect(screen.getByRole('link', { name: 'DOI 10.1000/example' })).toHaveAttribute(
      'href',
      'https://doi.org/10.1000/example',
    )
    expect(screen.getByTestId('finding-citations').children).toHaveLength(3)
  })

  it('uses registry review surfaces and opens the controlled note editor', async () => {
    renderWithProviders(<ProjectReviewPanel workspace={workspace} showDocument={false} />)

    expect(await screen.findByTestId('research-finding')).toHaveAttribute('data-slot', 'frame-panel')
    expect(screen.getByRole('combobox', { name: 'Choose a project section' })).toHaveAttribute(
      'data-slot',
      'select-trigger',
    )

    const addFinding = screen.getByRole('button', { name: 'Add finding/source' })
    expect(addFinding).toHaveAttribute('data-slot', 'dialog-trigger')
    fireEvent.click(addFinding)

    expect(await screen.findByRole('dialog')).toHaveAttribute('data-slot', 'dialog-content')
    expect(screen.getByRole('textbox', { name: 'Short title' })).toHaveFocus()
  })
})
