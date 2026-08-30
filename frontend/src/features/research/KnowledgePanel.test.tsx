import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { KnowledgePanel } from './KnowledgePanel'

const api = vi.hoisted(() => ({
  archive: vi.fn(),
  create: vi.fn(),
  search: vi.fn(),
  update: vi.fn(),
}))

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    projectId: 'project-one',
    activeProject: { id: 'project-one', name: 'Project one', summary: 'Summary' },
  }),
}))

vi.mock('../../lib/api/copilot', () => ({
  archiveCopilotKnowledgeEntry: api.archive,
  createCopilotKnowledgeEntry: api.create,
  searchCopilotKnowledge: api.search,
  updateCopilotKnowledgeEntry: api.update,
}))

describe('KnowledgePanel', () => {
  beforeEach(() => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
    api.search.mockResolvedValue({
      items: [{
        knowledge_entry_id: 'entry-one',
        project_id: 'project-one',
        title: 'Curated route',
        category: 'workflow',
        subcategory: 'design',
        summary: 'A source-backed route.',
        content: 'Detailed source-backed route.',
        tags_json: ['manual', 'curated'],
        source_type: 'curated',
        citation: 'DOI:10.1000/example',
        confidence: 'curated',
        metadata_json: {},
        version: 7,
        created_at: '2026-07-26T00:00:00Z',
        updated_at: '2026-07-26T00:00:00Z',
      }],
      next_cursor: null,
    })
    api.update.mockResolvedValue({
      knowledge_entry_id: 'entry-one',
      project_id: 'project-one',
      title: 'Curated route',
      category: 'workflow',
      summary: 'A source-backed route.',
      content: 'Detailed source-backed route.',
      tags_json: ['manual', 'curated'],
      source_type: 'curated',
      confidence: 'curated',
      metadata_json: {},
      version: 8,
      created_at: '2026-07-26T00:00:00Z',
      updated_at: '2026-07-26T00:00:01Z',
    })
  })

  afterEach(() => {
    cleanup()
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('uses registry surfaces and preserves versioned updates', async () => {
    const { container } = renderWithProviders(<KnowledgePanel />)

    expect(container.querySelectorAll('[data-slot="frame"]').length).toBe(2)
    expect(screen.getByPlaceholderText('Search knowledge for this project')).toHaveAttribute(
      'data-slot',
      'input',
    )

    fireEvent.click(await screen.findByRole('button', { name: /Curated route/ }))
    expect(screen.getByRole('textbox', { name: 'Content' })).toHaveAttribute('data-slot', 'textarea')
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(api.update).toHaveBeenCalledWith(
      'entry-one',
      expect.objectContaining({ title: 'Curated route' }),
      7,
    ))
  })
})
