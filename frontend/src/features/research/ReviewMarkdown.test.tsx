import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { ReviewMarkdown } from './ReviewMarkdown'

const LONG = [
  '# De novo binder design methods',
  '## 1. Premises',
  'Body.',
  '## 2. Design principles',
  'Body.',
  '```bash',
  '## not a heading, this is a shell comment',
  '```',
  '## 3. Model stack',
  '| Task | Primary |',
  '| --- | --- |',
  '| Backbone | RFdiffusion |',
  '## 4. Target preparation',
  'Body.',
].join('\n')

describe('ReviewMarkdown', () => {
  afterEach(cleanup)

  it('indexes the sections of a long document and links each to its heading', () => {
    const { container } = render(<ReviewMarkdown>{LONG}</ReviewMarkdown>)

    const links = [...container.querySelectorAll('nav a')]
    expect(links.map((link) => link.textContent)).toEqual([
      '1. Premises',
      '2. Design principles',
      '3. Model stack',
      '4. Target preparation',
    ])
    for (const link of links) {
      const id = link.getAttribute('href')!.slice(1)
      expect(container.querySelector(`h2#${id}`)?.textContent).toBe(link.textContent)
    }
  })

  it('scrolls within the correct document without replacing the application hash', () => {
    const { container } = render(<><ReviewMarkdown>{LONG}</ReviewMarkdown><ReviewMarkdown>{LONG}</ReviewMarkdown></>)
    const ids = [...container.querySelectorAll('h2')].map((h) => h.id)
    expect(new Set(ids).size).toBe(ids.length)
    const links = container.querySelectorAll('nav a')
    const target = document.getElementById(links[4].getAttribute('href')!.slice(1))!
    const scroll = vi.fn()
    target.scrollIntoView = scroll
    const hash = window.location.hash
    fireEvent.click(links[4])
    expect(scroll).toHaveBeenCalledWith({ block: 'start' })
    expect(window.location.hash).toBe(hash)
  })

  it('does not treat a ## line inside a fenced block as a section', () => {
    const { container } = render(<ReviewMarkdown>{LONG}</ReviewMarkdown>)

    expect(container.querySelectorAll('nav a')).toHaveLength(4)
    expect(screen.getByText(/this is a shell comment/)).toBeInTheDocument()
  })

  it('leaves short entries without an index', () => {
    const { container } = render(
      <ReviewMarkdown>{'# Search strategy\n\n## Sources\n\nBody.'}</ReviewMarkdown>,
    )

    expect(container.querySelector('nav')).toBeNull()
  })

  it('renders GFM tables with a scroll container so wide tables never widen the page', () => {
    const { container } = render(<ReviewMarkdown>{LONG}</ReviewMarkdown>)

    const table = container.querySelector('table')
    expect(table).not.toBeNull()
    expect(container.querySelector('th')?.textContent).toBe('Task')
  })
})

describe('traceable inline citations', () => {
  afterEach(cleanup)
  const citation = { entity_id: 'chunk-one', label: 'Saved paper', url: 'https://example.org/paper', document_id: 'doc-one', chunk_id: 'chunk-one', content_kind: 'database_abstract', content_checksum_sha256: 'a'.repeat(64), retrieval_trace_id: 'trace-one', excerpt: 'The measured result.', review_status: 'pending_review' }

  it('links only an explicit marker at its original position and opens its exact evidence', () => {
    const { container } = render(<ReviewMarkdown citations={[citation]}>{'Supported result.[cite:1] Unverified hypothesis.'}</ReviewMarkdown>)
    const paragraph = container.querySelector('p')!
    expect(paragraph.textContent).toBe('Supported result.[1] Unverified hypothesis.')
    const marker = screen.getByRole('link', { name: 'View source 1' })
    fireEvent.click(marker)
    const detail = document.getElementById(marker.getAttribute('href')!.slice(1))!
    expect(detail.querySelector('button')).toHaveAttribute('aria-expanded', 'true')
    expect(detail).toHaveTextContent('Database abstract')
    expect(detail).toHaveTextContent('The measured result.')
    expect(detail).toHaveTextContent('a'.repeat(64))
    expect(container.querySelectorAll('sup')).toHaveLength(1)
  })

  it('never assigns consulted sources to unmarked sentences or invents missing references', () => {
    const { container } = render(<ReviewMarkdown citations={[citation]}>{'No mapping. Unknown [cite:9]. Code `[cite:1]`.'}</ReviewMarkdown>)
    expect(container.querySelector('sup')).toBeNull()
    expect(container).toHaveTextContent('Unknown [cite:9]')
    expect(container.querySelector('code')).toHaveTextContent('[cite:1]')
  })

  it('does not turn authored links into citation markers by matching their URL', () => {
    const { container } = render(<ReviewMarkdown citations={[citation]}>{'[Ordinary link](#bda-citation-1) Supported.[cite:1]'}</ReviewMarkdown>)
    expect(screen.getByRole('link', { name: 'Ordinary link' }).closest('sup')).toBeNull()
    expect(container.querySelectorAll('sup')).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'View source 1' })).toHaveTextContent('[1]')
  })

  it('resolves legacy evidence tags only when every provenance field agrees', () => {
    const tag = `[document_id=doc-one; chunk_id=chunk-one; content_kind=database_abstract; content_checksum_sha256=${'a'.repeat(64)}; retrieval_trace_id=trace-one]`
    const { container } = render(<ReviewMarkdown citations={[citation]}>{`Result.${tag} Other.${tag.replace('trace-one', 'wrong-trace')}`}</ReviewMarkdown>)
    expect(container.querySelectorAll('sup')).toHaveLength(1)
    expect(container).toHaveTextContent('retrieval_trace_id=wrong-trace')
  })

  it('does not offer unsafe external citation links', () => {
    render(<ReviewMarkdown citations={[{ ...citation, url: 'javascript:alert(1)' }]}>{'Result.[cite:1]'}</ReviewMarkdown>)
    expect(screen.queryByRole('link', { name: /Open original source/ })).not.toBeInTheDocument()
  })

  it('resolves the public bibliography numbering without guessing array positions', () => {
    const citations = [9, 10, 11, 36, 37].map((number) => ({ ...citation, entity_id: `R${number}`, bibliography_number: String(number) }))
    const { container } = render(<ReviewMarkdown citations={citations}>{'Pain.[9–11] Structure.[36,37] Missing.[41–44]'}</ReviewMarkdown>)
    expect(container.querySelectorAll('sup')).toHaveLength(5)
    expect(container.querySelector('p')).toHaveTextContent('Pain.[1][2][3] Structure.[4][5] Missing.[41–44]')
  })

  it('keeps project navigation and source metadata in the same citation detail', () => {
    const source = { ...citation, source_type: 'research_workspace', workspace_type: 'structure', label: "{'zh': '结构来源', 'en': 'Structure source'}" }
    render(<MemoryRouter><ReviewMarkdown citations={[source]} projectId="project/one">{'Result.[cite:1]'}</ReviewMarkdown></MemoryRouter>)
    fireEvent.click(screen.getByRole('link', { name: 'View source 1' }))
    expect(screen.getByRole('button', { name: '[1] Structure source' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'View project material' })).toHaveAttribute('href', '/research?tab=structures&project=project%2Fone')
    expect(screen.getByRole('link', { name: 'Open original source · Structure source' })).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText('The measured result.')).toBeInTheDocument()
    expect(screen.getAllByTestId('citation-details')).toHaveLength(1)
  })
})
