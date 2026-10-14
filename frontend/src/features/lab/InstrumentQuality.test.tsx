import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { InstrumentQuality } from './InstrumentQuality'
import { reviewInstrumentAnalysis, type AnalysisRecord } from '../../lib/api/wetlab'

vi.mock('../../lib/api/wetlab', () => ({ reviewInstrumentAnalysis: vi.fn() }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const quality = { version: 'instrument-qc-v1', review_required: true, checks: [
  { code: 'inferred_phase_boundaries', status: 'review' as const, message: 'Verify instrument phases', details: {} },
], metrics: {}, interpretation: 'Diagnostic, not proof of binding' }
const record: AnalysisRecord = { experiment_result_id: 'r', experiment_type: 'bli_affinity', analysis_version: 'qc1',
  value: 3, unit: 'nM', source_artifact_id: 'a', version: 4, qc_review: { status: 'pending' } }
const mount = (input: Partial<React.ComponentProps<typeof InstrumentQuality>> = {}) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    <InstrumentQuality quality={quality} record={record} projectId="p" onReviewed={vi.fn()} {...input} />
  </QueryClientProvider>,
)

describe('instrument QC review', () => {
  it('requires a rationale and reviews the displayed record version', async () => {
    vi.mocked(reviewInstrumentAnalysis).mockResolvedValue({ experiment_result_id: 'r', version: 5,
      review: { status: 'accepted' }, candidate_metric_recorded: true })
    const onReviewed = vi.fn()
    mount({ onReviewed })
    expect(screen.getByRole('button', { name: 'Accept fit QC' })).toBeDisabled()
    expect(screen.getByText(/does not validate binding/)).toBeInTheDocument()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Protocol phases and raw signal checked' } })
    fireEvent.click(screen.getByRole('button', { name: 'Accept fit QC' }))
    await waitFor(() => expect(reviewInstrumentAnalysis).toHaveBeenCalledWith('p', record, true, 'Protocol phases and raw signal checked'))
    await waitFor(() => expect(onReviewed).toHaveBeenCalledWith(expect.objectContaining({ version: 5, qc_review: { status: 'accepted' } })))
  })
  it('keeps unavailable measurements rejectable but not quantitatively acceptable', () => {
    mount({ record: { ...record, value: null } })
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Insufficient dissociation data' } })
    expect(screen.getByRole('button', { name: 'Accept fit QC' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject this fit' })).toBeEnabled()
  })
  it('does not treat historical missing diagnostics as accepted', () => {
    mount({ quality: null })
    expect(screen.getByText(/missing diagnostics do not mean QC passed/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Accept fit QC' })).not.toBeInTheDocument()
  })
})
