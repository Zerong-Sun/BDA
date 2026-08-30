import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/renderWithProviders'
import { FAQPage } from './FAQ'

describe('FAQPage', () => {
  it('renders localized FAQ page content and sections', () => {
    renderWithProviders(<FAQPage />)

    expect(screen.getByRole('heading', { name: /Frequently asked questions/i })).toBeInTheDocument()
    expect(screen.getByText('Help center')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Platform overview and first steps/i })).toHaveAttribute(
      'data-slot',
      'accordion-trigger',
    )
    expect(screen.getByRole('button', { name: /Literature review and evidence/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Common execution problems/i })).toBeInTheDocument()
  })
})
