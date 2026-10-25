import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { BotRecords } from './BotRecords'

const records = vi.hoisted(() => ({ get: vi.fn(), download: vi.fn() }))
vi.mock('../../lib/api/botRecords', () => ({ getBotRecords: records.get, downloadBotRecords: records.download }))
vi.mock('../../lib/i18n', () => ({ useI18n: () => ({ language: 'en', t: {
  shared: { apiState: { loadingDefault: 'Loading records', backendUnavailable: 'Unavailable', retry: 'Retry' } },
} }) }))
const citation = { title: 'Primary source about this measurement', source_type: 'scientific_literature',
  url: 'https://example.org/paper', document_id: 'doc-1', chunk_id: 'chunk-1',
  content_kind: 'open_access_full_text', excerpt: 'The recorded excerpt supports this limited claim.',
  locator: 'Results paragraph 4', review_status: 'pending_review' }
function result(citations: unknown[] = [citation], content = 'A bounded claim [cite:1].') {
  return { project_id: 'project-1', bot_id: 'researcher', record_id: 'record-1', sha256: 'abc123',
    updated_at: '2026-10-16T00:00:00Z', total: 1, matched: 1, offset: 0, items: [{
      kind: 'message', id: 'message-1', bot: 'researcher', status: 'completed',
      created_at: '2026-10-16T00:00:00Z', updated_at: '2026-10-16T00:00:00Z', source_version: 1,
      content, references: [], citations,
    }] }
}
beforeEach(() => { vi.resetAllMocks(); records.get.mockResolvedValue(result()) })

describe('BotRecords source citations', () => {
  it('opens the saved source from a message citation while preserving source review status', async () => {
    renderWithProviders(<BotRecords projectId="project-1" botId="researcher" />)
    const marker = await screen.findByRole('link', { name: 'View source 1' })
    fireEvent.click(marker)
    expect(screen.getByRole('link', { name: /Open original source/ })).toHaveAttribute('href', citation.url)
    expect(screen.getByText(citation.excerpt)).toBeVisible()
    expect(screen.getByText('Awaiting review')).toBeVisible()
    expect(screen.getByText(citation.document_id)).toBeVisible()
  })

  it('does not shift citation numbering when a malformed source record is present', async () => {
    records.get.mockResolvedValue(result([null, citation], 'Keep unresolved [cite:1] separate from [cite:2].'))
    renderWithProviders(<BotRecords projectId="project-1" botId="researcher" />)
    expect(await screen.findByText('Keep unresolved [cite:1] separate from [cite:2].')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'View source 1' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'View source 2' })).not.toBeInTheDocument()
  })
})
