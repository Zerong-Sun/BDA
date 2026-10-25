import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { interpretResults, type InterpretationReasoning } from '../lib/api/copilot'
import { ResultsPage } from './Results'

vi.mock('../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({
  projectId: useAppStore(state => state.activeProjectId), activeProject: null,
}) }))
vi.mock('../lib/api/copilot', () => ({ interpretResults: vi.fn() }))
vi.mock('../lib/api/projects', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api/projects')>(),
  getResultsSummary: vi.fn(async () => null), getDeliveryPackageOrNull: vi.fn(async () => null), createDeliveryPackage: vi.fn(),
}))
vi.mock('../lib/api/artifacts', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api/artifacts')>(),
  listProjectArtifacts: vi.fn(async (projectId: string) => [{
    id: `${projectId}-evidence`, project_id: projectId, filename: 'evidence.json', artifact_type: 'file',
    content_type: 'application/json', status: 'available', size_bytes: 2, checksum_sha256: 'a'.repeat(64),
    lineage: {}, version: 1, created_at: '2026-10-25T00:00:00Z', updated_at: '2026-10-25T00:00:00Z',
  }]),
}))
vi.mock('../components/ui/NextStep', () => ({ NextStep: () => null }))
vi.mock('../features/lab/SavedInstrumentReviews', () => ({ SavedInstrumentReviews: () => null }))

const interpretation: InterpretationReasoning = {
  subject_id: 'a', subject_type: 'project', headline: 'Private interpretation of project A',
  signals: [], decision: 'insufficient_data', decision_rationale: 'Only A evidence', next_actions: [], caveats: [],
}
beforeEach(() => {
  useAppStore.setState({ activeProjectId: 'a', language: 'en', appMode: 'application' })
  vi.mocked(interpretResults).mockReset()
})
afterEach(cleanup)

it('removes an existing project interpretation when switching projects', async () => {
  vi.mocked(interpretResults).mockResolvedValue(interpretation)
  renderWithProviders(<ResultsPage />)
  const interpret = screen.getByRole('button', { name: /interpret/i })
  await waitFor(() => expect(interpret).toBeEnabled())
  fireEvent.click(interpret)
  await screen.findByText(interpretation.headline)
  act(() => useAppStore.getState().setActiveProjectId('b'))
  expect(screen.queryByText(interpretation.headline)).not.toBeInTheDocument()
})

it('does not display a delayed interpretation for A after switching to B', async () => {
  let finish!: (value: InterpretationReasoning) => void
  vi.mocked(interpretResults).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  renderWithProviders(<ResultsPage />)
  const interpret = screen.getByRole('button', { name: /interpret/i })
  await waitFor(() => expect(interpret).toBeEnabled())
  fireEvent.click(interpret)
  await waitFor(() => expect(interpretResults).toHaveBeenCalledWith('a'))
  act(() => useAppStore.getState().setActiveProjectId('b'))
  await act(async () => finish(interpretation))
  expect(screen.queryByText(interpretation.headline)).not.toBeInTheDocument()
})
