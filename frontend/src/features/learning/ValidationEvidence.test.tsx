import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { FeatureExplanation, ValidationEvidence } from './ValidationEvidence'

afterEach(cleanup)
const copy = (_cn: string, en: string) => en

describe('learning scientific evidence presentation', () => {
  it('shows actual observations separately from held-out predictions and names leakage limits', () => {
    renderWithProviders(<ValidationEvidence unit="nM" copy={copy} evaluation={{
      feature_version: 'sequence-order-v1', data_quality: { family_overlap_fold_count: 2, batch_overlap_fold_count: 1 },
      folds: [{ held_out_group: 'family-one', test_predictions: [{ sequence_sha256: 'abcdef0123456789', observed: 4, predicted: 5 }] }],
    }} />)
    expect(screen.getByText(/461 dimensions/)).toBeInTheDocument()
    expect(screen.getByText(/Homology isolation is not established/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Compare held-out predictions with observations' }))
    expect(screen.getByRole('columnheader', { name: 'Observed' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Held-out prediction' })).toBeInTheDocument()
    expect(screen.getByText('4.000 nM')).toBeInTheDocument()
    expect(screen.getByText('5.000 nM')).toBeInTheDocument()
    expect(screen.getByText('1.000 nM')).toBeInTheDocument()
  })

  it('explains historical composition snapshots without implying an embedding model', () => {
    renderWithProviders(<FeatureExplanation version={undefined} copy={copy} />)
    expect(screen.getByText(/21 dimensions/)).toBeInTheDocument()
    expect(screen.getByText(/ignores residue order/)).toBeInTheDocument()
  })
})
