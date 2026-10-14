import { act, cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GuidePage } from '../../app/Guide'
import { renderWithProviders } from '../../test/renderWithProviders'
import { WorkflowMap } from './WorkflowMap'
import { useAppStore } from '../../lib/store/appStore'

beforeEach(() => {
  sessionStorage.clear()
  useAppStore.setState({ language: 'en' })
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
  vi.unstubAllGlobals()
})

describe('WorkflowMap stepper structure', () => {
  it('uses immediate jumps and still tracks reading progress with reduced motion', () => {
    let notify: IntersectionObserverCallback = () => undefined
    const observe = vi.fn()
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback) { notify = callback }
      observe = observe
      unobserve = vi.fn()
      disconnect = vi.fn()
    })
    const scroll = vi.fn()
    const originalScroll = HTMLElement.prototype.scrollIntoView
    HTMLElement.prototype.scrollIntoView = scroll
    const changed = vi.fn()
    try {
      renderWithProviders(<WorkflowMap activeStep={1} onActiveStepChange={changed} />)
      expect(observe).toHaveBeenCalledTimes(11)
      const section = document.querySelector<HTMLElement>('[data-step="2"]')!
      act(() => notify([{ target: section, isIntersecting: true, intersectionRatio: 0.7 } as unknown as IntersectionObserverEntry], {} as IntersectionObserver))
      expect(changed).toHaveBeenCalledWith(2)
      fireEvent.click(screen.getAllByRole('tab', { name: /^Step 3:/ })[0])
      expect(scroll).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' })
      expect(changed).toHaveBeenCalledWith(3)
    } finally {
      if (originalScroll) HTMLElement.prototype.scrollIntoView = originalScroll
      else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
    }
  })

  it('shows useful step diagrams, keeps details optional, and returns to the same project', () => {
    sessionStorage.setItem('bda_token', 'test-token')
    window.location.hash = '/guide?project=project-one'
    renderWithProviders(<GuidePage />)
    expect(screen.getAllByRole('list', { name: 'How this step works' })).toHaveLength(11)
    expect(screen.queryByText(/animationComponent|animation placeholder/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Inputs, outputs and checks' }).every((button) => button.getAttribute('aria-expanded') === 'false')).toBe(true)
    const actionLinks = [...document.querySelectorAll('.guide-station a')]
    expect(actionLinks).toHaveLength(11)
    expect(actionLinks.every((link) => link.getAttribute('href')?.includes('project=project-one'))).toBe(true)
    expect(screen.queryByRole('link', { name: /login/i })).not.toBeInTheDocument()
    const projectLinks = screen.getAllByRole('link').filter((link) => link.getAttribute('href')?.includes('/projects'))
    expect(projectLinks.length).toBeGreaterThan(0)
    expect(projectLinks.every((link) => link.getAttribute('href')?.includes('project=project-one'))).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Take the interface tour' }))
    expect(useAppStore.getState().tourMenuOpen).toBe(true)
    expect(window.location.hash).toContain('/projects?project=project-one')
  })
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
