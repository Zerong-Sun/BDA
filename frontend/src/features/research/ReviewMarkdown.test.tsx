import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
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
