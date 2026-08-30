import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
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
})
