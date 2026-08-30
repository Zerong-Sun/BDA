import { cleanup, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GuidePage } from '../../app/Guide'
import { renderWithProviders } from '../../test/renderWithProviders'

beforeEach(() => {
  vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
    matches: query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }))
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('WorkflowMap stepper structure', () => {
  it('keeps sticky progress outside Frame overflow and every horizontal step reachable', () => {
    renderWithProviders(<GuidePage />)

    const map = screen.getByRole('region', { name: 'Workflow stations' })
    expect(map.closest('[data-slot="frame-panel"]')).toBeNull()
    const guidePage = map.closest<HTMLElement>('.guide-page')
    expect(guidePage).not.toHaveClass('overflow-x-hidden')
    expect(guidePage).toHaveClass('overflow-x-clip')

    const viewport = document.querySelector<HTMLElement>('[data-guide-progress-viewport="horizontal"]')
    expect(viewport).toHaveClass('overflow-x-auto')
    expect(within(viewport!).getAllByRole('tab')).toHaveLength(11)
  })

  it('creates unique trigger ids and valid panels across both desktop steppers', () => {
    renderWithProviders(<GuidePage />)

    const tabs = screen.getAllByRole('tab')
    const ids = tabs.map((tab) => tab.id)
    expect(new Set(ids).size).toBe(ids.length)

    for (const tab of tabs) {
      const panelId = tab.getAttribute('aria-controls')
      expect(panelId).toBeTruthy()
      const panel = document.getElementById(panelId!)
      expect(panel).toHaveAttribute('role', 'tabpanel')
      expect(panel).toHaveAttribute('aria-labelledby', tab.id)
    }
  })
})
