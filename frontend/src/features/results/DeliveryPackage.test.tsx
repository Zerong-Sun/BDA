import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DeliveryPackage } from './DeliveryPackage'

describe('DeliveryPackage', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
  })

  afterEach(() => cleanup())

  it('shows a strict empty state without fabricated package contents', () => {
    renderWithProviders(<DeliveryPackage packageData={null} />)

    expect(screen.getByText('No delivery package has been generated from verified project artifacts yet.')).toBeInTheDocument()
    expect(screen.queryByText('PD1Binder_c4361')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Download full ZIP package' })).not.toBeInTheDocument()
    expect(screen.queryByText('Order 64 variants: 40 exploitation, 24 exploration')).not.toBeInTheDocument()
  })

  it('keeps package creation explicit and prevents duplicate pending requests', () => {
  const created = vi.fn()
  const data = { id: 'package', project_id: 'project', name: 'Research export', status: 'pending',
    selection: { format: 'ro-crate-1.1', frozen_at: '2026-10-11' }, artifact_id: null, error: null, version: 1,
    created_at: '2026-10-11', updated_at: '2026-10-11' }
  const view = renderWithProviders(<DeliveryPackage packageData={null} writable onCreate={created} />)
  fireEvent.click(screen.getByRole('button', { name: 'Create research delivery package' }))
  expect(created).toHaveBeenCalledTimes(1)
  view.rerender(<DeliveryPackage packageData={data} writable onCreate={created} />)
  expect(screen.getByRole('button', { name: 'Create research delivery package' })).toBeDisabled()
  expect(screen.getByText(/RO-Crate 1.1/)).toBeInTheDocument()
})
})
