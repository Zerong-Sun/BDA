import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { ErrorBoundary } from './ErrorBoundary'
import { AppShell } from '../../App'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { server } from '../../test/mocks/handlers'

describe('ErrorBoundary', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v2/health/ready', () =>
        HttpResponse.json({
          status: 'ok',
          service: 'bda-api',
          checks: {},
        }),
      ),
    )
  })

  it('renders fallback when a child throws', () => {
    function Broken(): never {
      throw new Error('boom')
    }

    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    )

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  it('keeps the application shell scroll-safe and min-width-safe', () => {
    useAppStore.setState({ copilotOpen: false, settingsOpen: false })
    const { container } = renderWithProviders(<AppShell />)

    const shell = container.querySelector('[data-slot="app-shell"]')
    const content = shell?.querySelector(':scope > div')
    const main = shell?.querySelector('main')
    expect(shell).toHaveClass('flex', 'min-h-screen', 'min-w-0', 'flex-col')
    expect(content).toHaveClass('min-h-0', 'flex-1', 'overflow-hidden')
    expect(main).toHaveClass('min-h-0', 'min-w-0', 'flex-1', 'overflow-y-auto')
  })
})
