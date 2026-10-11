import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { LiteratureWorkbench } from './LiteratureWorkbench'
import { EvidenceNoteEditor } from './EvidenceNoteEditor'
import { evidenceMarkdown, noteDraft, type EvidenceNote, type LiteratureReference } from './evidenceNotes'

const api = vi.hoisted(() => ({ list: vi.fn(), save: vi.fn(), review: vi.fn(), chunks: vi.fn() }))
vi.mock('../../lib/api/evidenceNotes', () => ({ listEvidenceNotes: api.list, saveEvidenceNote: api.save, reviewEvidenceNote: api.review }))
vi.mock('../../lib/api/literatureSources', () => ({ listSavedLiteratureChunks: api.chunks }))
vi.mock('../../lib/hooks/useProjectAccess', () => ({ useProjectAccess: () => ({ data: { permissions: { write: true } } }) }))
vi.mock('./LiteratureSourceDetails', () => ({ LiteratureSourceDetails: () => <p>Original source records</p> }))
vi.mock('./EvidenceSourceRetrieval', () => ({ EvidenceSourceRetrieval: () => null }))

const references: LiteratureReference[] = [
  { document_id: 'doc-one', title: { default: 'First paper' }, ref_id: 'R01', status: 'available', doi: '10.1000/first', url: 'https://example.org/first' },
  { document_id: 'doc-two', title: { default: 'Second paper' }, ref_id: 'R02', status: 'available', url: 'https://example.org/second' },
]
const first: EvidenceNote = {
  id: 'note-one', document_id: 'doc-one', document_title: 'First paper', argument: 'A shared project argument',
  paper_claim: 'The paper reports an observation', interpretation: 'Our separately stated inference',
  limitations: 'Only tested in mice', relation: 'supports', quote: 'Original English words.', locator: 'Results, Figure 2',
  source_url: 'https://example.org/first', source_ref: { chunk_id: 'chunk-one', chunk_position: 0, content_kind: 'database_abstract', selector: [{ type: 'TextPositionSelector', start: 4, end: 27 }] },
  anchor_status: 'matched', review_status: 'pending', reviewed_by: null, reviewed_at: null, version: 7,
  created_at: '2026-10-11T00:00:00Z', updated_at: '2026-10-11T00:00:00Z',
}
const second: EvidenceNote = { ...first, id: 'note-two', document_id: 'doc-two', document_title: 'Second paper', relation: 'contradicts', quote: 'Conflicting original words.' }

beforeEach(() => {
  vi.clearAllMocks()
  useAppStore.setState({ language: 'en', appMode: 'application' })
  api.list.mockResolvedValue({ items: [first, second], next_cursor: null })
  api.chunks.mockResolvedValue({ items: [], next_cursor: null })
  api.save.mockResolvedValue(first)
  api.review.mockResolvedValue({ ...first, review_status: 'accepted', version: 8 })
})
afterEach(cleanup)

describe('literature evidence workbench', () => {
  it('shows original language, linked paper, author claim, inference and limits without expanding metadata', async () => {
    useAppStore.setState({ language: 'zh' })
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    const card = await screen.findByTestId('evidence-note-card')
    expect(within(card).getByText(first.quote)).toBeVisible()
    expect(within(card).getByText(first.paper_claim)).toBeVisible()
    expect(within(card).getByText(first.interpretation)).toBeVisible()
    expect(within(card).getByText(first.limitations)).toBeVisible()
    expect(within(card).getByRole('link', { name: 'First paper' })).toHaveAttribute('href', first.source_url)
    expect(within(card).getByText('已与保存原文匹配')).toBeVisible()
    expect(within(card).getByText(/仅摘要/)).toBeVisible()
  })

  it('puts supporting and conflicting sources under the same argument and searches the evidence', async () => {
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    await screen.findByTestId('evidence-note-card')
    fireEvent.click(screen.getByRole('button', { name: 'By argument' }))
    expect(screen.getAllByTestId('evidence-note-card')).toHaveLength(2)
    expect(screen.getByText('Contradicts / limits')).toBeVisible()
    fireEvent.change(screen.getByRole('textbox', { name: 'Find papers and evidence' }), { target: { value: 'Conflicting original' } })
    expect(screen.getAllByTestId('evidence-note-card')).toHaveLength(1)
    expect(screen.getByText(second.quote)).toBeVisible()
  })

  it('marks old bibliography records as gaps without inventing original text', async () => {
    api.list.mockResolvedValue({ items: [first], next_cursor: null })
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    await screen.findByTestId('evidence-note-card')
    fireEvent.click(screen.getByRole('button', { name: 'Needs annotation' }))
    expect(screen.queryByTestId('evidence-note-card')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Second paper' })).toBeVisible()
    expect(screen.getByText('This paper has no project evidence card yet')).toBeVisible()
  })

  it('does not turn a failed or incomplete fetch into a claim that evidence is absent', async () => {
    api.list.mockRejectedValue(new Error('unavailable'))
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('does not mean the papers are unannotated')
    expect(screen.getByRole('button', { name: 'Needs annotation' })).toBeDisabled()
    expect(screen.queryByText('This paper has no project evidence card yet')).not.toBeInTheDocument()
  })

  it('loads remaining cursor pages before enabling missing-evidence counts', async () => {
    api.list.mockImplementation(async (_id, cursor) => ({ items: cursor ? [second] : [first], next_cursor: cursor ? null : 'next' }))
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    fireEvent.click(await screen.findByRole('button', { name: /Load more evidence/ }))
    await waitFor(() => expect(api.list).toHaveBeenCalledWith('project-one', 'next'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Needs annotation' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'By argument' }))
    expect(screen.getAllByTestId('evidence-note-card')).toHaveLength(2)
  })

  it('keeps read-only mode free of write controls', async () => {
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} readOnly />)
    await screen.findByTestId('evidence-note-card')
    expect(screen.queryByRole('button', { name: 'Add argument & passage' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Accept evidence' })).not.toBeInTheDocument()
  })

  it('reviews the displayed version rather than fetching and silently accepting a newer edit', async () => {
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Accept evidence' }))
    await waitFor(() => expect(api.review).toHaveBeenCalledWith('note-one', 7, 'accepted'))
  })

  it('disables acceptance when the original source changed', async () => {
    api.list.mockResolvedValue({ items: [{ ...first, anchor_status: 'changed' }], next_cursor: null })
    renderWithProviders(<LiteratureWorkbench projectId="project-one" references={references} />)
    expect(await screen.findByRole('button', { name: 'Accept evidence' })).toBeDisabled()
    expect(screen.getByText(/Source changed/)).toBeVisible()
  })
})

describe('evidence editing and export', () => {
  it('reuses the exact existing argument so different papers can be compared together', async () => {
    renderWithProviders(<EvidenceNoteEditor projectId="project-one" reference={references[0]} note={first} argumentChoices={['Another shared argument']} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('combobox', { name: 'Reuse an existing argument' }))
    fireEvent.click(await screen.findByRole('option', { name: 'Another shared argument' }))
    expect(screen.getByRole('textbox', { name: '1 · Our project argument' })).toHaveValue('Another shared argument')
    expect(screen.getByRole('textbox', { name: 'Original quote (source language)' })).toHaveValue(first.quote)
  })

  it('retains the original quote separately when editing an interpretation', async () => {
    const close = vi.fn()
    renderWithProviders(<EvidenceNoteEditor projectId="project-one" reference={references[0]} note={first} onClose={close} />)
    fireEvent.change(screen.getByRole('textbox', { name: '4 · How this informs our argument' }), { target: { value: 'Revised interpretation' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save for review' }))
    await waitFor(() => expect(api.save).toHaveBeenCalledWith('doc-one', expect.objectContaining({ quote: first.quote, interpretation: 'Revised interpretation', quote_start: 4 }), first))
    expect(close).toHaveBeenCalled()
  })

  it('preserves an unsaved draft and displays a concurrent edit conflict', async () => {
    api.save.mockRejectedValue(new Error('Evidence note changed; reload before editing'))
    renderWithProviders(<EvidenceNoteEditor projectId="project-one" reference={references[0]} note={first} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save for review' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('reload before editing')
    expect(screen.getByRole('textbox', { name: 'Original quote (source language)' })).toHaveValue(first.quote)
  })

  it('exports provenance, limitations and pending status with each original quote', () => {
    const result = evidenceMarkdown([first], false)
    expect(result).toContain('> Original English words.')
    expect(result).toContain('(https://example.org/first)')
    expect(result).toContain('Only tested in mice')
    expect(result).toContain('pending')
    expect(result).toContain('version=7')
    expect(noteDraft(first).quote_start).toBe(4)
  })
})
