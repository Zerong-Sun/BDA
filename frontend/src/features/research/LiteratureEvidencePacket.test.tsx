import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { LiteratureEvidencePacket } from './LiteratureEvidencePacket'

const metadata = { evidence_packet: {
  schema: 'literature-evidence-packet-v1', source_url: 'https://example.org/paper',
  arguments: [{ project_argument: 'Curated claim', source_ids: ['t1'] }],
  analysis: { arguments: [{ project_argument: 'Model draft', source_ids: ['p1'] }] },
  passages: [{ id: 'p1', text: 'Observed source passage.' }],
  tables: [{ id: 't1', caption: 'Measured affinity', rows: [
    [{ text: 'KD', header: true, colspan: 2 }], [{ text: 'Sample' }, { text: '121.2 nM' }],
  ], footnotes: 'n = 3' }],
} }

describe('paper evidence source display', () => {
  it('retains curated claims alongside model drafts and resolves table source text', async () => {
    renderWithProviders(<LiteratureEvidencePacket documentId="paper" metadata={metadata} />)
    fireEvent.click(screen.getByRole('button', { name: /Project arguments/ }))
    expect(await screen.findByRole('heading', { name: 'Curated claim' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Model draft' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Source: t1' }))
    expect(await screen.findByText('Measured affinity KD Sample 121.2 nM n = 3')).toBeVisible()
  })
  it('preserves table headers, merged cells, footnotes and safe source links', async () => {
    renderWithProviders(<LiteratureEvidencePacket documentId="paper" metadata={metadata} />)
    expect(screen.getByRole('link', { name: 'Original source and license' })).toHaveAttribute('href', 'https://example.org/paper')
    fireEvent.click(screen.getByRole('button', { name: /Original tables with headers/ }))
    const table = await screen.findByRole('table')
    expect(within(table).getByRole('columnheader', { name: 'KD' })).toHaveAttribute('colspan', '2')
    expect(within(table).getByRole('cell', { name: '121.2 nM' })).toBeVisible()
    expect(screen.getByText('n = 3')).toBeVisible()
  })
})
