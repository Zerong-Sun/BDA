import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { LiteratureSourceDetails } from './LiteratureSourceDetails'

const sources = vi.hoisted(() => ({ chunks: vi.fn(), traces: vi.fn() }))
vi.mock('../../lib/api/literatureSources', () => ({ listSavedLiteratureChunks: sources.chunks, listSavedLiteratureTraces: sources.traces }))

beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  sources.chunks.mockReset().mockImplementation(async (_id: string, cursor?: string) => ({
    items: [{ id: cursor ? 'chunk-two' : 'chunk-one', content: cursor ? 'Second original excerpt.' : 'Original evidence, not an automatic translation.', position: cursor ? 1 : 0, version: 1 }], next_cursor: cursor ? null : 'next-page',
  }))
  sources.traces.mockReset().mockResolvedValue({ items: [], next_cursor: null })
})
afterEach(cleanup)

describe('saved literature evidence', () => {
  it('loads saved records only on demand and lets the reader inspect all pages', async () => {
    renderWithProviders(<LiteratureSourceDetails projectId="project-one" documentId="document-one" metadata={{ content_provenance: { content_kind: 'database_abstract', content_checksum_sha256: 'a'.repeat(64) } }} />)
    expect(sources.chunks).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Verify: saved excerpts and retrieval records' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Excerpt 1 · v1' }))
    expect(screen.getByText('Original evidence, not an automatic translation.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '[1] Currently indexed source snapshot' }))
    expect(screen.getByText('Database abstract')).toBeInTheDocument()
    await waitFor(() => expect(sources.chunks).toHaveBeenCalledWith('document-one', 'next-page'))
    expect(await screen.findByRole('button', { name: 'Excerpt 2 · v1' })).toBeInTheDocument()
  })

  it('distinguishes a retrieval error from missing evidence and localizes the interface', async () => {
    useAppStore.setState({ language: 'zh' })
    sources.chunks.mockRejectedValue(new Error('unavailable'))
    renderWithProviders(<LiteratureSourceDetails projectId="project-two" documentId="document-two" metadata={{}} abstract="Original English abstract." />)
    fireEvent.click(screen.getByRole('button', { name: '查证：已存片段与检索记录' }))
    expect(await screen.findByText('片段读取失败；不能将错误视为没有证据。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '数据库中的摘要（原文）' }))
    expect(screen.getByText('Original English abstract.')).toBeInTheDocument()
    expect(screen.queryByText('尚未保存正文或摘要片段。')).not.toBeInTheDocument()
  })

  it('finishes UUID pagination before showing source order and translates chronological trace summaries', async () => {
    useAppStore.setState({ language: 'zh' })
    sources.chunks.mockImplementation(async (_id: string, cursor?: string) => ({
      items: [{ id: cursor ? 'earlier-source' : 'later-source', content: 'Source text.', position: cursor ? 0 : 1, version: 1 }], next_cursor: cursor ? null : 'next-page',
    }))
    sources.traces.mockResolvedValue({ items: [
      { id: 'late', source: 'crossref', stage: 'metadata_verification', status: 'completed', created_at: '2026-09-30T09:30:00Z', request_json: {} },
      { id: 'early', source: 'europe_pmc', stage: 'search_hit', status: 'completed', created_at: '2026-09-30T09:00:00Z', request_json: {} },
    ], next_cursor: null })
    renderWithProviders(<LiteratureSourceDetails projectId="project-one" documentId="document-one" metadata={{}} />)
    fireEvent.click(screen.getByRole('button', { name: '查证：已存片段与检索记录' }))
    await screen.findByRole('button', { name: '片段 1 · v1' })
    expect(screen.getAllByRole('button', { name: /^片段 / }).map((button) => button.textContent)).toEqual(['片段 1 · v1', '片段 2 · v1'])
    const traceButtons = screen.getAllByRole('button', { name: /^(Europe PMC|Crossref) ·/ })
    expect(traceButtons[0]).toHaveTextContent('Europe PMC · 命中记录 · 完成')
    expect(traceButtons[1]).toHaveTextContent('Crossref · 元数据核验 · 完成')
    expect(screen.queryByText(/metadata_verification/)).not.toBeInTheDocument()
    expect(screen.getByText('已保存的原文片段 (2)')).toBeInTheDocument()
  })

  it('keeps partial evidence visible after a page error and allows an explicit retry', async () => {
    sources.chunks.mockImplementation(async (_id: string, cursor?: string) => {
      if (cursor) throw new Error('next page unavailable')
      return { items: [{ id: 'partial', content: 'Already saved evidence.', position: 5, version: 1 }], next_cursor: 'next-page' }
    })
    renderWithProviders(<LiteratureSourceDetails projectId="project-one" documentId="document-one" metadata={{}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Verify: saved excerpts and retrieval records' }))
    expect(await screen.findByRole('button', { name: 'Retry remaining excerpts' })).toBeInTheDocument()
    expect(screen.getByText('Saved source excerpts (1 loaded, incomplete)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Excerpt 6 · v1' })).toBeInTheDocument()
    expect(sources.chunks).toHaveBeenCalledTimes(2)
    fireEvent.click(screen.getByRole('button', { name: 'Retry remaining excerpts' }))
    await waitFor(() => expect(sources.chunks).toHaveBeenCalledTimes(3))
  })
})
