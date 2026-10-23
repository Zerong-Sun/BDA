import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { ToolsPage } from './Tools'

const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
const scrollIntoView = vi.fn()
beforeEach(() => {
  window.location.hash = '/tools?tool=protein-properties&source=review'
  useAppStore.setState({ language: 'en', activeProjectId: '' })
  scrollIntoView.mockClear()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
  server.use(http.get('/api/v2/projects', () => HttpResponse.json({ items: [], next_cursor: null })))
})
afterEach(cleanup)
afterAll(() => {
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})

describe('Tools page navigation', () => {
  it('preserves drafts, scrolls to the work area and focuses the new tool on a category change', async () => {
    renderWithProviders(<ToolsPage />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Sequence' }), { target: { value: 'ACDE' } })
    expect(scrollIntoView).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Protein A280 → concentration' }))
    const heading = screen.getByRole('heading', { name: 'Protein A280 → concentration' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start' })
    expect(window.location.hash).toContain('source=review')
    fireEvent.click(screen.getByRole('button', { name: 'Protein mass & extinction' }))
    expect(screen.getByRole('textbox', { name: 'Sequence' })).toHaveValue('ACDE')
  })

  it('recovers an unknown linked tool through the top selector without losing unrelated query parameters', async () => {
    window.location.hash = '/tools?tool=missing&source=review'
    renderWithProviders(<ToolsPage />)
    expect(screen.getByRole('status')).toHaveTextContent('linked tool is unavailable')
    fireEvent.click(screen.getByRole('combobox', { name: 'Choose lab tool' }))
    const option = await screen.findByRole('option', { name: 'Centrifuge RPM ⇄ RCF' })
    fireEvent.pointerDown(option, { button: 0 })
    fireEvent.pointerUp(option, { button: 0 })
    fireEvent.click(option)
    await waitFor(() => expect(window.location.hash).toContain('tool=centrifuge'))
    expect(window.location.hash).toContain('source=review')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Centrifuge RPM ⇄ RCF' })).toBeInTheDocument()
  })
})
