import type { ComponentProps } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../test/renderWithProviders'
import { LearningLifecycle } from './LearningLifecycle'

const api = vi.hoisted(() => ({ importObservations: vi.fn(), receiveLearningBatch: vi.fn() }))
vi.mock('../lib/api/learning', () => api)
afterEach(() => { cleanup(); vi.clearAllMocks() })

type Props = ComponentProps<typeof LearningLifecycle>
const base = { version: 1, created_at: '2026-10-05T00:00:00Z', updated_at: '2026-10-05T00:00:00Z', project_id: 'p', created_by: 'u' }
const measurement = { candidate_id: 'c', candidate_ref: 'Synthetic candidate', conclusion: null, experiment_type: 'assay', failure_reason: null, pass_status: 'unknown', source_artifact_id: 'file1', unit: 'nM', value: null, batch_key: 'b' }
function props(overrides: Partial<Props> = {}): Props {
  return {
    projectId: 'p', study: { ...base, id: 's', name: 'Synthetic', assay_id: 'a', currency: 'USD' } as Props['study'],
    assay: { ...base, id: 'a', name: 'Assay', unit: 'nM', conditions: {}, method: 'Synthetic' },
    evidence: [], batches: [], decisions: [], results: [], workflows: [],
    artifacts: [{ ...base, id: 'file1', filename: 'synthetic.csv', status: 'available', artifact_type: 'experiment_data', checksum_sha256: 'a'.repeat(64), content_type: 'text/csv', lineage: {}, size_bytes: 100 }],
    writable: true, experimentWritable: true, busy: false, perform: async (action) => { await action() }, copy: (_cn, en) => en,
    ...overrides,
  }
}

describe('learning experiment handoff', () => {
  it('requires a successful dry run before importing and clears it after import', async () => {
    api.importObservations.mockResolvedValue({ dry_run: true, row_count: 2, observations: [], result_ids: [] })
    renderWithProviders(<LearningLifecycle {...props()} />)
    expect(screen.queryByRole('button', { name: 'Import validated observations' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Validate file' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Import validated observations' }))
    await waitFor(() => expect(api.importObservations).toHaveBeenCalledTimes(2))
    expect(api.importObservations.mock.calls).toEqual([
      ['p', { assay_id: 'a', artifact_id: 'file1', dry_run: true }],
      ['p', { assay_id: 'a', artifact_id: 'file1', dry_run: false }],
    ])
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Import validated observations' })).not.toBeInTheDocument())
  })

  it('prevents experimental writes for a read-only user', () => {
    renderWithProviders(<LearningLifecycle {...props({ experimentWritable: false })} />)
    expect(screen.getByRole('button', { name: 'Validate file' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Validate file' }))
    expect(api.importObservations).not.toHaveBeenCalled()
  })

  it.each(['new-default', 'changed-version', 'removed'] as const)('requires revalidation when source refresh changes the file: %s', async (change) => {
    api.importObservations.mockResolvedValue({ dry_run: true, row_count: 2, observations: [], result_ids: [] })
    const initial = props()
    const { rerender } = renderWithProviders(<LearningLifecycle {...initial} />)
    fireEvent.click(screen.getByRole('button', { name: 'Validate file' }))
    expect(await screen.findByRole('button', { name: 'Import validated observations' })).toBeInTheDocument()
    const first = initial.artifacts[0]
    const artifacts = change === 'new-default'
      ? [{ ...first, id: 'file2', filename: 'other.csv' }, first]
      : change === 'changed-version' ? [{ ...first, version: 2 }] : []
    rerender(<LearningLifecycle {...initial} artifacts={artifacts} />)
    expect(screen.queryByRole('button', { name: 'Import validated observations' })).not.toBeInTheDocument()
    expect(api.importObservations).toHaveBeenCalledTimes(1)
  })

  it('receives every active batch result including failures, excluding withdrawn and other batches', async () => {
    const batch = { ...base, id: 'batch', study_id: 's', decision_id: 'd', campaign_id: 'campaign', round_id: 'round', digest: 'hash', manifest: { batch_key: 'learning:batch', round_number: 1 }, receipt: null }
    const result = (id: string, batchKey: string, withdrawal = false, status = 'measured'): Props['results'][number] => ({ ...base, ...measurement, id, batch_key: batchKey, result_metadata: { learning: { status }, ...(withdrawal ? { learning_withdrawal: { rationale: 'Bad instrument' } } : {}) } })
    api.receiveLearningBatch.mockResolvedValue({})
    renderWithProviders(<LearningLifecycle {...props({ batches: [batch], results: [result('ok', 'learning:batch'), result('failed', 'learning:batch', false, 'failed'), result('withdrawn', 'learning:batch', true), result('other', 'unrelated')] })} />)
    fireEvent.change(screen.getByLabelText(/Reported total experimental cost/), { target: { value: '12.34' } })
    fireEvent.change(screen.getByLabelText('Round conclusions and deviations'), { target: { value: 'One sample failed; cost includes all samples' } })
    fireEvent.click(screen.getByRole('button', { name: 'Receive results' }))
    await waitFor(() => expect(api.receiveLearningBatch).toHaveBeenCalledWith('p', batch, { result_ids: ['ok', 'failed'], actual_cost_cents: 1234, note: 'One sample failed; cost includes all samples' }))
  })

  it('flags historical evidence after its source version changes', () => {
    const evidence = { ...base, id: 'e', study_id: 's', kind: 'fact', statement: 'Old finding', sources: { results: [{ id: 'r', version: 1 }] }, withdrawal: null } as Props['evidence'][number]
    renderWithProviders(<LearningLifecycle {...props({ evidence: [evidence], results: [{ ...base, ...measurement, id: 'r', version: 2, result_metadata: { learning_withdrawal: { rationale: 'Correction' } } }] })} />)
    expect(screen.getByRole('heading', { name: /Sources changed; review required/ })).toBeInTheDocument()
    expect(screen.getByText('Old finding')).toBeInTheDocument()
  })
})
