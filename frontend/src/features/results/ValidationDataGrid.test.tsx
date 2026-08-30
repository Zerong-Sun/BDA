import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ExperimentResult } from '../../lib/schemas/candidate'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ValidationTable } from './ValidationTable'

const results: ExperimentResult[] = [
  {
    id: 'result_a',
    project_id: 'proj_test',
    candidate_id: 'cand_a',
    candidate_ref: null,
    source_artifact_id: null,
    batch_key: null,
    experiment_type: 'BLI',
    pass_status: 'pass',
    value: 0.8,
    unit: 'nM',
    conclusion: 'Strong binding',
    failure_reason: null,
    result_metadata: {},
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 'result_b',
    project_id: 'proj_test',
    candidate_id: 'cand_b',
    candidate_ref: null,
    source_artifact_id: null,
    batch_key: null,
    experiment_type: 'SEC',
    pass_status: 'fail',
    value: null,
    unit: null,
    conclusion: null,
    failure_reason: 'Aggregation',
    result_metadata: {},
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
]

describe('ValidationTable ReUI data grid', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
  })

  afterEach(() => cleanup())

  it('uses the ReUI grid while preserving candidate filtering and clear behavior', () => {
    const onClearCandidate = vi.fn()
    renderWithProviders(
      <ValidationTable
        results={results}
        candidateId="cand_a"
        onClearCandidate={onClearCandidate}
      />,
    )

    expect(screen.getByRole('table')).toHaveAttribute('data-slot', 'data-grid-table')
    expect(screen.getByText('Strong binding')).toBeInTheDocument()
    expect(screen.queryByText('Aggregation')).not.toBeInTheDocument()
    const gridContainer = screen.getByRole('table').closest('[data-slot="data-grid"]')
    expect(gridContainer).toHaveClass('[&>div]:h-full', '[&>div]:min-h-0')
    expect(gridContainer?.querySelector('[data-slot="data-grid-scroll-area"]')).toHaveClass('h-full', 'min-h-0')

    const clear = screen.getByRole('button', { name: 'Clear' })
    expect(clear).toHaveAttribute('data-slot', 'button')
    fireEvent.click(clear)
    expect(onClearCandidate).toHaveBeenCalledOnce()
  })

  it('keeps the localized empty state inside the data-grid contract', () => {
    renderWithProviders(<ValidationTable results={[]} />)

    expect(screen.getByRole('table')).toHaveAttribute('data-slot', 'data-grid-table')
    expect(screen.getByText('No experiment results uploaded yet.')).toBeInTheDocument()
  })
})
