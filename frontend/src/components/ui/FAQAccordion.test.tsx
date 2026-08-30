import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FAQAccordion, type FAQAccordionSectionData } from './FAQAccordion'

const mockSections: FAQAccordionSectionData[] = [
  {
    id: 'gettingStarted',
    label: 'Getting started',
    title: 'Platform overview',
    items: [
      {
        id: 'whatIsPlatform',
        question: 'What is this platform for?',
        answer: 'BDA Workbench automates protein binder design.',
      },
      {
        id: 'whoIsItFor',
        question: 'Who is it designed for?',
        answer: 'Computational biologists and protein engineers.',
      },
    ],
  },
  {
    id: 'troubleshooting',
    label: 'Troubleshooting',
    title: 'Common problems',
    items: [
      {
        id: 'backendNotRunning',
        question: 'Backend not running',
        answer: 'Start the API on port 8100.',
      },
    ],
  },
]

function getSectionByTitle(title: string) {
  const heading = screen.getByRole('heading', { name: title })
  const section = heading.closest('section')
  if (!section) throw new Error(`Section not found for title: ${title}`)
  return section
}

afterEach(() => {
  cleanup()
})

describe('FAQAccordion', () => {
  it('renders empty state when no sections are provided', () => {
    render(<FAQAccordion sections={[]} emptyMessage="No FAQ content." />)

    expect(screen.getByRole('status')).toHaveTextContent('No FAQ content.')
  })

  it('expands and collapses sections independently', () => {
    render(<FAQAccordion sections={mockSections} />)

    const overviewSection = getSectionByTitle('Platform overview')
    const problemsSection = getSectionByTitle('Common problems')

    const overviewToggle = within(overviewSection).getAllByRole('button')[0]
    const problemsToggle = within(problemsSection).getAllByRole('button')[0]

    expect(overviewToggle).toHaveAttribute('aria-expanded', 'false')
    expect(problemsToggle).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(overviewToggle)
    expect(overviewToggle).toHaveAttribute('aria-expanded', 'true')
    expect(problemsToggle).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(problemsToggle)
    expect(overviewToggle).toHaveAttribute('aria-expanded', 'true')
    expect(problemsToggle).toHaveAttribute('aria-expanded', 'true')
  })

  it('disables FAQ items until the parent section is open', () => {
    render(<FAQAccordion sections={mockSections} />)

    const overviewSection = getSectionByTitle('Platform overview')
    const questionButton = within(overviewSection).getByRole('button', {
      name: /What is this platform for\?/i,
      hidden: true,
    })
    expect(questionButton).toBeDisabled()

    fireEvent.click(within(overviewSection).getAllByRole('button')[0])
    expect(questionButton).not.toBeDisabled()

    fireEvent.click(questionButton)
    expect(screen.getByText('BDA Workbench automates protein binder design.')).toBeInTheDocument()
    expect(questionButton).toHaveAttribute('aria-expanded', 'true')
  })

  it('toggles FAQ items with keyboard', () => {
    render(<FAQAccordion sections={mockSections} />)

    const overviewSection = getSectionByTitle('Platform overview')
    fireEvent.click(within(overviewSection).getAllByRole('button')[0])

    const questionButton = within(overviewSection).getByRole('button', {
      name: /What is this platform for\?/i,
    })

    fireEvent.keyDown(questionButton, { key: ' ' })
    expect(questionButton).toHaveAttribute('aria-expanded', 'true')

    fireEvent.keyDown(questionButton, { key: 'Enter' })
    expect(questionButton).toHaveAttribute('aria-expanded', 'false')
  })

  it('toggles sections with keyboard', () => {
    render(<FAQAccordion sections={mockSections} />)

    const overviewSection = getSectionByTitle('Platform overview')
    const sectionButton = within(overviewSection).getAllByRole('button')[0]

    fireEvent.keyDown(sectionButton, { key: 'Enter' })
    expect(sectionButton).toHaveAttribute('aria-expanded', 'true')
  })
})
