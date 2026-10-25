import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { ProteinLibrary } from './ProteinLibrary'

vi.mock('../../lib/hooks/useProjectAccess', () => ({
  useProjectAccess: () => ({ isSuccess: true, data: { permissions: { write: false } } }),
}))
vi.mock('../research/AttachToGoalButton', () => ({ AttachToGoalButton: () => null }))
vi.mock('../../lib/api/wetlab', () => ({
  listProteins: async () => ({ items: [{
    id: 'protein-one', name: 'Reference construct', fingerprint: 'sha256:example-fingerprint',
    length: 120, molecular_weight: 13000, ext_coeff_reduced: 1490, candidate_id: null,
  }] }),
  createProtein: vi.fn(), importFasta: vi.fn(),
}))
beforeEach(() => useAppStore.setState({ language: 'en', appMode: 'application' }))
afterEach(cleanup)

it('keeps construct properties visible and reveals identifiers without changing edit access', async () => {
  renderWithProviders(<ProteinLibrary projectId="project-one" />)
  expect(await screen.findByText('Reference construct')).toBeVisible()
  expect(screen.getByText('120')).toBeVisible()
  expect(screen.queryByText('sha256:example-fingerprint')).not.toBeInTheDocument()
  expect(screen.getByText(/Adding constructs requires project edit access/)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Show sequence identifiers' }))
  expect(screen.getByText('sha256:example-fingerprint')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Hide sequence identifiers' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Hide sequence identifiers' }))
  expect(screen.queryByText('sha256:example-fingerprint')).not.toBeInTheDocument()
  expect(screen.getByText('Reference construct')).toBeVisible()
  expect(screen.getByText(/Adding constructs requires project edit access/)).toBeVisible()
})
