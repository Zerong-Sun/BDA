import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DecisionReview } from './DecisionReview'

describe('DecisionReview', () => {
  afterEach(cleanup)

  it('uses registry controls and disables every mutation while saving', () => {
    renderWithProviders(
      <DecisionReview
        decisionId="decision-one"
        roundNumber={2}
        patch={{ models: {} }}
        onSave={vi.fn()}
        onReview={vi.fn()}
        saving
      />,
    )

    expect(screen.getByRole('textbox', { name: 'Round 2 parameter patch' })).toHaveAttribute(
      'data-slot',
      'textarea',
    )
    for (const button of screen.getAllByRole('button')) {
      expect(button).toHaveAttribute('data-slot', 'button')
      expect(button).toBeDisabled()
    }
  })
})
