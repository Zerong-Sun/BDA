import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ResearchPage } from './Research'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'

const state = vi.hoisted(() => ({ projectId: 'a' }))
vi.mock('../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({
  projectId: state.projectId,
  activeProject: { id: state.projectId, name: `Project ${state.projectId}`, status: 'archived', summary: 'Saved scope' },
}) }))
vi.mock('../lib/hooks/useProjectTargetStructure', () => ({ useProjectTargetStructure: () => ({ data: null }) }))
vi.mock('../features/research/ProjectReviewPanel', () => ({ ProjectReviewPanel: () => null }))
vi.mock('../features/research/GenerateSimilarResearchPanel', () => ({ GenerateSimilarResearchPanel: () => null }))
vi.mock('../features/research/ResearchDecisionCenter', () => ({ ResearchDecisionCenter: () => null }))
vi.mock('../features/research/ResearchGoalsPanel', () => ({ ResearchGoalsPanel: () => null }))
vi.mock('../lib/api/researchWorkspace', async importOriginal => ({
  ...await importOriginal<typeof import('../lib/api/researchWorkspace')>(),
  getResearchWorkspace: async (id: string) => ({
    project: { id, name: { en: `Project ${id}` }, project_type: 'research' },
    review_document: { id: `report-${id}`, title: { en: `Report ${id}` }, content: { en: `## Results\nResult ${id}\n## Next steps\nCondition ${id}\n## Sources\nFull report detail ${id}` }, status: 'accepted', version: 1, updated_at: '2026-10-19T00:00:00Z' },
    review_sections: [], graph_nodes: [], graph_edges: [{ id: `edge-${id}`, source: 'one', target: 'two', source_label: { en: 'one' }, target_label: { en: 'two' }, summary: { en: `Evidence ${id}` }, context: { en: 'Saved context' }, predicate: 'binds', assertion: 'hypothesis', evidence_grade: 'C', reference_ids: [], source_urls: [], review_status: 'pending_review' }],
    references: [], structures: [], research_targets: [], methods: [], datasets: [], counts: {},
  }),
}))

beforeEach(() => { state.projectId = 'a'; useAppStore.setState({ language: 'en', appMode: 'application' }) })
afterEach(cleanup)

it('clears evidence search when returning to a cached project', async () => {
  window.location.hash = '/research?project=a&tab=evidence'
  const view = renderWithProviders(<ResearchPage />)
  await screen.findByText('edge-a')
  state.projectId = 'b'; view.rerender(<ResearchPage />)
  await screen.findByText('edge-b')
  fireEvent.change(screen.getByRole('textbox', { name: 'Search subject, relation, object, or context' }), { target: { value: 'only-project-b' } })
  expect(screen.queryByText('edge-b')).not.toBeInTheDocument()
  state.projectId = 'a'; view.rerender(<ResearchPage />)
  expect(await screen.findByText('edge-a')).toBeVisible()
  expect(screen.getByRole('textbox', { name: 'Search subject, relation, object, or context' })).toHaveValue('')
  expect(screen.queryByText('edge-b')).not.toBeInTheDocument()
})

it('keeps cached report content and expanded details scoped to their project', async () => {
  window.location.hash = '/research?project=a&tab=goals'
  const view = renderWithProviders(<ResearchPage />)
  expect(await screen.findByText('Result a')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Read full report' }))
  expect(await screen.findByText('Full report detail a')).toBeVisible()
  state.projectId = 'b'; view.rerender(<ResearchPage />)
  expect(await screen.findByText('Result b')).toBeVisible()
  expect(screen.queryByText('Full report detail a')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Full report and cited sources' })).toHaveAttribute('aria-expanded', 'false')
  state.projectId = 'a'; view.rerender(<ResearchPage />)
  expect(await screen.findByText('Result a')).toBeVisible()
  expect(screen.queryByText('Result b')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Full report and cited sources' })).toHaveAttribute('aria-expanded', 'false')
})
