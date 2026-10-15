import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { KnowledgePanel } from './KnowledgePanel'
import { useAppStore } from '../../lib/store/appStore'

const api = vi.hoisted(() => ({
  archive: vi.fn(),
  create: vi.fn(),
  search: vi.fn(),
  update: vi.fn(),
}))

const access = vi.hoisted(() => ({ writable: true }))
vi.mock('../../lib/hooks/useProjectAccess', () => ({
  useProjectAccess: () => ({ data: { permissions: { write: access.writable } } }),
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
    useAppStore.setState({ appMode: 'application', language: 'en' })
    access.writable = true
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
        review_status: 'pending_review',
        source: { citation: 'DOI:10.1000/example', source_message_id: 'message-one' },
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
      expect.objectContaining({ title: 'Curated route', citation: undefined,
        source: { citation: 'DOI:10.1000/example', source_message_id: 'message-one' },
        confidence: 'unassessed', review_status: 'pending_review' }),
      7,
    ))
  })

  it('searches across the server and loads the next matching page', async () => {
    const nextEntry = { ...((await api.search()).items[0]), knowledge_entry_id: 'entry-two', title: 'An older route' }
    api.search.mockClear()
    api.search.mockImplementation(async (_project: string, _query: string, _type: string, cursor?: string) => ({
      items: cursor ? [nextEntry] : [{ ...nextEntry, knowledge_entry_id: 'entry-one', title: 'A recent route' }],
      next_cursor: cursor ? null : 'page-two',
    }))
    renderWithProviders(<KnowledgePanel />)
    await screen.findByRole('button', { name: /A recent route/ })
    expect(api.search).toHaveBeenCalledWith('project-one', '', undefined, undefined)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search project knowledge' }), { target: { value: '抗体_100%' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Filter entry type' }), { target: { value: 'copilot_draft' } })
    await waitFor(() => expect(api.search).toHaveBeenCalledWith('project-one', '抗体_100%', 'copilot_draft', undefined))
    fireEvent.click(await screen.findByRole('button', { name: 'Load more knowledge' }))
    await screen.findByRole('button', { name: /An older route/ })
    expect(api.search).toHaveBeenLastCalledWith('project-one', '抗体_100%', 'copilot_draft', 'page-two')
    expect(screen.getByRole('button', { name: /A recent route/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Load more knowledge' })).not.toBeInTheDocument()
  })

  it('preserves structured citations and shows a conflict without silently retrying', async () => {
    const source = { citation: { doi: '10.1000/example' }, source_message_id: 'message-one' }
    api.search.mockResolvedValue({ items: [{ ...((await api.search()).items[0]), citation: null, source }], next_cursor: null })
    api.update.mockRejectedValue(new Error('Version conflict: reload before saving'))
    renderWithProviders(<KnowledgePanel />)
    fireEvent.click(await screen.findByRole('button', { name: /Curated route/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Original source and citation record' }))
    expect(screen.getByText(/"source_message_id": "message-one"/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByText('Version conflict: reload before saving')
    expect(api.update).toHaveBeenCalledWith('entry-one', expect.objectContaining({ source, citation: undefined }), 7)
    expect(api.update).toHaveBeenCalledTimes(1)
  })

  it('does not grant edit controls to project readers', async () => {
    access.writable = false
    renderWithProviders(<KnowledgePanel />)
    fireEvent.click(await screen.findByRole('button', { name: /Curated route/ }))
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Archive' })).toBeDisabled()
  })
})
