import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { initialTourState, useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { TourOverlay } from './TourOverlay'

const projectContext = vi.hoisted(() => ({
  projectId: 'pd1-demo',
  projects: [] as Array<Record<string, unknown>>,
  setProjectId: vi.fn(),
}))

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => projectContext,
}))

const originalScrollIntoView = HTMLElement.prototype.scrollIntoView

function setReducedMotion(matches: boolean) {
  const motionAddEventListener = vi.fn()
  const motionRemoveEventListener = vi.fn()
  const matchMedia = vi.fn((query: string): MediaQueryList => ({
    matches: matches && query === '(prefers-reduced-motion: reduce)',
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: query === '(prefers-reduced-motion: reduce)'
      ? motionAddEventListener
      : vi.fn(),
    removeEventListener: query === '(prefers-reduced-motion: reduce)'
      ? motionRemoveEventListener
      : vi.fn(),
    dispatchEvent: vi.fn(() => false),
  }))
  Object.defineProperty(window, 'matchMedia', { configurable: true, writable: true, value: matchMedia })
  return { motionAddEventListener, motionRemoveEventListener }
}

function startAtProjectSelector() {
  useAppStore.getState().startTour('projects')
  useAppStore.getState().advanceTour()
}

describe('TourOverlay', () => {
  beforeEach(() => {
    window.location.hash = '/experiments?project=pd1-demo'
    projectContext.projectId = 'pd1-demo'
    projectContext.projects = []
    projectContext.setProjectId.mockReset()
    useAppStore.setState({
      language: 'en',
      appMode: 'application',
      copilotOpen: false,
      settingsOpen: false,
      tourState: initialTourState,
      tourMenuOpen: false,
    })
    setReducedMotion(false)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    // Restore timer spies while the fake clock still owns the globals, then
    // return to the real clock. Reversing these calls reinstalls the spied fake
    // timer functions and contaminates every test that follows.
    vi.useRealTimers()
    if (originalScrollIntoView) {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView
    } else {
      Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
    }
  })

  it('renders welcome and missing-anchor steps in a controlled modal Dialog with controlled ReUI Stepper progress', async () => {
    useAppStore.getState().startTour('projects')
    renderWithProviders(<TourOverlay />)

    const dialog = await screen.findByRole('dialog', { name: 'Welcome to the interface tour' })
    expect(dialog).toHaveAttribute('data-slot', 'dialog-content')
    expect(dialog).toHaveClass('motion-reduce:animate-none', 'motion-reduce:duration-0')
    expect(dialog.querySelector('[data-slot="stepper"]')).toBeInTheDocument()
    expect(dialog.querySelector('[data-slot="stepper-nav"]')).toHaveAttribute('data-state', '1')
    expect(dialog.querySelector('[data-slot="stepper-panel"]')).toHaveAttribute('data-state', '1')
    expect(dialog.querySelector('[data-slot="stepper-content"]')).toHaveAttribute('data-state', '1')
    expect(screen.getAllByRole('tab')).toHaveLength(4)
    expect(screen.getAllByRole('tab').every((tab) => tab.hasAttribute('disabled'))).toBe(true)
    expect(dialog.querySelectorAll('[data-slot="stepper-separator"]')).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Next' })).toHaveAttribute('data-slot', 'button')
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Pause tour' })).toHaveAttribute('data-slot', 'dialog-close')
  })

  it('uses DialogClose semantics for modal coaching and restores its pre-dialog focus origin', async () => {
    useAppStore.getState().startTour('projects')
    renderWithProviders(
      <>
        <button type="button" autoFocus>Tour origin</button>
        <TourOverlay />
      </>,
    )
    // The modal correctly makes its page siblings inaccessible while open, so
    // retain the connected origin by text rather than querying the hidden
    // background through the accessibility tree.
    const origin = screen.getByText('Tour origin')
    const pause = await screen.findByRole('button', { name: 'Pause tour' })
    expect(pause).toHaveAttribute('data-slot', 'dialog-close')

    fireEvent.click(pause)
    expect(await screen.findByRole('dialog', { name: 'Interface tour' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    await waitFor(() => expect(origin).toHaveFocus())
  })

  it('anchors a controlled non-modal Popover without stealing focus or blocking target interaction', async () => {
    vi.useFakeTimers()
    startAtProjectSelector()
    const onTargetClick = vi.fn()
    renderWithProviders(
      <>
        <button type="button" autoFocus data-tour-id="project-selector" onClick={onTargetClick}>
          Project selector
        </button>
        <TourOverlay />
      </>,
    )
    const target = screen.getByRole('button', { name: 'Project selector' })

    await act(async () => {
      await Promise.resolve()
    })
    const coach = document.querySelector<HTMLElement>('[data-slot="popover-content"]')
    expect(coach).toBeInTheDocument()
    expect(coach).toHaveAttribute('data-tour-anchor', 'project-selector')
    expect(target).toHaveFocus()

    fireEvent.pointerDown(document.body)
    fireEvent.click(document.body)
    expect(coach).toBeInTheDocument()
    expect(useAppStore.getState().tourState.stepId).toBe('project-selector')

    fireEvent.click(target)
    expect(onTargetClick).toHaveBeenCalledTimes(1)
    act(() => vi.advanceTimersByTime(180))
    expect(useAppStore.getState().tourState.stepId).toBe('project-library')
  })

  it('falls back to a modal Dialog and localized Alert when an anchor cannot be found', async () => {
    vi.useFakeTimers()
    startAtProjectSelector()
    renderWithProviders(<TourOverlay />)

    await act(async () => {
      vi.advanceTimersByTime(5_000)
      await Promise.resolve()
    })

    expect(screen.getByRole('dialog', { name: 'Active project' })).toHaveAttribute('data-slot', 'dialog-content')
    expect(screen.getByRole('alert')).toHaveTextContent(
      'This control is not available in the current view. You can skip this step.',
    )
    expect(screen.getByRole('button', { name: 'Next' })).toHaveAttribute('data-slot', 'button')
  })

  it('advances only after the required safe target is clicked', async () => {
    vi.useFakeTimers()
    startAtProjectSelector()
    renderWithProviders(
      <>
        <button type="button" data-tour-id="project-selector">Project selector</button>
        <TourOverlay />
      </>,
    )

    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByText('Active project')).toBeInTheDocument()
    expect(useAppStore.getState().tourState.stepId).toBe('project-selector')
    fireEvent.click(screen.getByText('Project selector'))
    expect(useAppStore.getState().tourState.stepId).toBe('project-selector')
    act(() => vi.advanceTimersByTime(180))
    expect(useAppStore.getState().tourState.stepId).toBe('project-library')
  })

  it('leaves final completion ownership with the persisted tour store', () => {
    setReducedMotion(true)
    useAppStore.setState({
      tourState: {
        status: 'active',
        sectionId: 'faq',
        stepId: 'faq-content',
        completedSections: ['projects', 'research', 'workflow', 'candidates', 'results', 'copilot-settings'],
        updatedAt: null,
      },
    })
    renderWithProviders(
      <>
        <button type="button" data-tour-id="faq-content">FAQ section</button>
        <TourOverlay />
      </>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'FAQ section' }))
    expect(useAppStore.getState()).toMatchObject({
      tourMenuOpen: false,
      tourState: {
        status: 'completed',
        completedSections: ['projects', 'research', 'workflow', 'candidates', 'results', 'copilot-settings', 'faq'],
      },
    })
  })

  it('uses reduced-motion positioning and advances a target-click step without a delay', async () => {
    setReducedMotion(true)
    startAtProjectSelector()
    const scrollIntoView = vi.fn()
    const onTargetClick = vi.fn()
    HTMLElement.prototype.scrollIntoView = scrollIntoView
    renderWithProviders(
      <>
        <button type="button" autoFocus data-tour-id="project-selector" onClick={onTargetClick}>
          Project selector
        </button>
        <TourOverlay />
      </>,
    )

    const target = screen.getByRole('button', { name: 'Project selector' })
    await waitFor(() => expect(
      document.querySelector<HTMLElement>('[data-slot="popover-content"]'),
    ).toBeInTheDocument())
    expect(document.querySelector<HTMLElement>('[data-slot="popover-content"]'))
      .toHaveClass('motion-reduce:animate-none', 'motion-reduce:duration-0')
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: 'auto',
      block: 'center',
      inline: 'nearest',
    }))
    fireEvent.click(target)
    expect(onTargetClick).toHaveBeenCalledTimes(1)
    expect(useAppStore.getState().tourState.stepId).toBe('project-library')
  })

  it('clears exact positioning and delayed-advance timers plus target listeners on unmount', () => {
    vi.useFakeTimers()
    const clearTimeout = vi.spyOn(window, 'clearTimeout')
    const clearInterval = vi.spyOn(window, 'clearInterval')
    const setTimeout = vi.spyOn(window, 'setTimeout')
    const setInterval = vi.spyOn(window, 'setInterval')
    startAtProjectSelector()

    const view = renderWithProviders(
      <>
        <button type="button" data-tour-id="project-selector">Project selector</button>
        <TourOverlay />
      </>,
    )
    const target = screen.getByRole('button', { name: 'Project selector' })
    const positioningTimerIndex = setTimeout.mock.calls.findIndex(([, delay]) => delay === 220)
    const positioningIntervalIndex = setInterval.mock.calls.findIndex(([, delay]) => delay === 125)
    const positioningTimer = setTimeout.mock.results[positioningTimerIndex]?.value
    const positioningInterval = setInterval.mock.results[positioningIntervalIndex]?.value
    expect(positioningTimer).toBeDefined()
    expect(positioningInterval).toBeDefined()
    fireEvent.click(target)
    const advanceTimerIndex = setTimeout.mock.calls.findIndex(([, delay]) => delay === 180)
    const advanceTimer = setTimeout.mock.results[advanceTimerIndex]?.value
    expect(advanceTimer).toBeDefined()

    view.unmount()

    expect(clearTimeout).toHaveBeenCalledWith(positioningTimer)
    expect(clearTimeout).toHaveBeenCalledWith(advanceTimer)
    expect(clearInterval).toHaveBeenCalledWith(positioningInterval)
    act(() => vi.runOnlyPendingTimers())
    expect(useAppStore.getState().tourState.stepId).toBe('project-selector')
  })

  it('removes the exact registered target-click callback when unmounted before a click', () => {
    startAtProjectSelector()
    const target = document.createElement('button')
    target.type = 'button'
    target.dataset.tourId = 'project-selector'
    target.textContent = 'External project selector'
    document.body.append(target)
    const addTargetListener = vi.spyOn(target, 'addEventListener')
    const removeTargetListener = vi.spyOn(target, 'removeEventListener')

    const view = renderWithProviders(<TourOverlay />)
    const registeredCallback = addTargetListener.mock.calls
      .find(([type]) => type === 'click')?.[1]
    expect(registeredCallback).toBeTypeOf('function')

    view.unmount()

    expect(removeTargetListener).toHaveBeenCalledWith('click', registeredCallback)
    target.remove()
  })

  it('removes the reduced-motion media listener and global keyboard listener on unmount', () => {
    const media = setReducedMotion(false)
    const addWindowListener = vi.spyOn(window, 'addEventListener')
    const removeWindowListener = vi.spyOn(window, 'removeEventListener')
    startAtProjectSelector()

    const view = renderWithProviders(<TourOverlay />)
    const motionListener = media.motionAddEventListener.mock.calls
      .find(([type]) => type === 'change')?.[1]
    const keyboardListener = addWindowListener.mock.calls
      .find(([type]) => type === 'keydown')?.[1]
    expect(motionListener).toBeTypeOf('function')
    expect(keyboardListener).toBeTypeOf('function')

    view.unmount()

    expect(media.motionRemoveEventListener).toHaveBeenCalledWith('change', motionListener)
    expect(removeWindowListener).toHaveBeenCalledWith('keydown', keyboardListener)
  })

  it('restores the anchored target after Pause then tour-menu Close', async () => {
    startAtProjectSelector()
    renderWithProviders(
      <>
        <button type="button" autoFocus data-tour-id="project-selector">Project selector</button>
        <TourOverlay />
      </>,
    )
    const target = screen.getByRole('button', { name: 'Project selector' })
    await act(async () => {
      await Promise.resolve()
    })
    const pause = screen.getByRole('button', { name: 'Pause tour' })
    fireEvent.click(pause)
    expect(screen.getByRole('dialog', { name: 'Interface tour' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    await waitFor(() => expect(target).toHaveFocus())
  })

  it('restores a connected anchor after a final button step opens then closes the chapter menu', async () => {
    useAppStore.setState({
      tourState: {
        ...initialTourState,
        status: 'active',
        sectionId: 'projects',
        stepId: 'main-navigation',
      },
    })
    renderWithProviders(
      <>
        <button type="button" autoFocus data-tour-id="main-navigation">Main navigation target</button>
        <TourOverlay />
      </>,
    )
    const target = screen.getByRole('button', { name: 'Main navigation target' })
    await act(async () => {
      await Promise.resolve()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByRole('dialog', { name: 'Interface tour' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    await waitFor(() => expect(target).toHaveFocus())
  })

  it('prefers the current final target after a prior button step stored an older focus fallback', async () => {
    setReducedMotion(true)
    useAppStore.setState({
      tourState: {
        ...initialTourState,
        status: 'active',
        sectionId: 'research',
        stepId: 'research-workspace',
      },
    })
    renderWithProviders(
      <>
        <button type="button" autoFocus data-tour-id="research-workspace">Research workspace target</button>
        <button type="button" data-tour-id="research-operations">Research operations target</button>
        <TourOverlay />
      </>,
    )

    await act(async () => {
      await Promise.resolve()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(
      document.querySelector('[data-slot="popover-content"]'),
    ).toHaveAttribute('data-tour-anchor', 'research-operations')

    const finalTarget = screen.getByRole('button', { name: 'Research operations target' })
    finalTarget.focus()
    fireEvent.click(finalTarget)
    expect(screen.getByRole('dialog', { name: 'Interface tour' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    await waitFor(() => expect(finalTarget).toHaveFocus())
  })

  it('skips with Escape, opens the tour menu, and returns focus when the menu closes', async () => {
    startAtProjectSelector()
    renderWithProviders(
      <>
        <button type="button" data-tour-id="project-selector">Project selector</button>
        <TourOverlay />
      </>,
    )
    await act(async () => {
      await Promise.resolve()
    })
    const target = screen.getByRole('button', { name: 'Project selector' })
    target.focus()
    fireEvent.keyDown(target, { key: 'Escape' })

    expect(useAppStore.getState().tourState.status).toBe('paused')
    expect(screen.getByRole('dialog', { name: 'Interface tour' })).toHaveAttribute('data-slot', 'dialog-content')
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(useAppStore.getState().tourMenuOpen).toBe(false)
    await waitFor(() => expect(target).toHaveFocus())
  })

  it('keeps route/project query synchronization and prepares Copilot then settings', async () => {
    useAppStore.getState().startTour('research')
    const view = renderWithProviders(<TourOverlay />)
    await waitFor(() => expect(window.location.hash).toContain('/research?tab=evidence&project=pd1-demo'))

    act(() => useAppStore.getState().startTour('copilot-settings'))
    await waitFor(() => expect(useAppStore.getState()).toMatchObject({ copilotOpen: true, settingsOpen: false }))
    act(() => useAppStore.getState().advanceTour())
    await waitFor(() => expect(useAppStore.getState()).toMatchObject({ copilotOpen: false, settingsOpen: true }))
    view.unmount()
  })

  it('updates copy in place when the language changes', async () => {
    useAppStore.getState().startTour('projects')
    renderWithProviders(<TourOverlay />)
    expect(await screen.findByText('Welcome to the interface tour')).toBeInTheDocument()
    act(() => useAppStore.setState({ language: 'zh' }))
    expect(await screen.findByText('欢迎使用界面导览')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '下一步' })).toBeInTheDocument()
    expect(useAppStore.getState().tourState.stepId).toBe('projects-welcome')
  })

  it('announces the current language while an anchored target is still resolving', async () => {
    startAtProjectSelector()
    useAppStore.setState({ language: 'zh' })
    renderWithProviders(<TourOverlay />)

    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByText('当前项目')).toHaveAttribute('aria-live', 'polite')
  })

  it('lists every chapter with registry Buttons and starts a selected chapter in the demo project', async () => {
    projectContext.projects = [{
      id: 'demo-project',
      name: 'PD-1 demo',
      source_project_key: 'PD1',
    }]
    useAppStore.setState({
      tourMenuOpen: true,
      tourState: { ...initialTourState, completedSections: ['research'] },
    })
    renderWithProviders(<TourOverlay />)

    const menu = await screen.findByRole('dialog', { name: 'Interface tour' })
    expect(menu).toHaveAttribute('data-slot', 'dialog-content')
    const chapterButtons = screen.getAllByTestId('tour-chapter')
    expect(chapterButtons).toHaveLength(7)
    expect(chapterButtons.every((button) => button.getAttribute('data-slot') === 'button')).toBe(true)

    const completedChapter = screen.getByRole('button', { name: 'Research workspace, Completed' })
    expect(completedChapter).toHaveAttribute('data-slot', 'button')
    fireEvent.click(completedChapter)
    expect(projectContext.setProjectId).toHaveBeenCalledWith('demo-project')
    expect(useAppStore.getState()).toMatchObject({
      appMode: 'demo',
      tourMenuOpen: false,
      tourState: { status: 'active', sectionId: 'research', stepId: 'research-tabs' },
    })
  })

  it('lets the controlled tour-menu Dialog own Escape even when an active tour is behind it', async () => {
    useAppStore.getState().startTour('projects')
    useAppStore.setState({ tourMenuOpen: true })
    renderWithProviders(<TourOverlay />)

    expect(await screen.findByRole('dialog', { name: 'Interface tour' })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(useAppStore.getState().tourMenuOpen).toBe(false))
    expect(useAppStore.getState().tourState.status).toBe('active')
  })

  it('restarts all progress through the demo project and shows bilingual missing-demo feedback', async () => {
    useAppStore.setState({
      tourMenuOpen: true,
      tourState: { ...initialTourState, status: 'paused', completedSections: ['faq'] },
    })
    const view = renderWithProviders(<TourOverlay />)
    fireEvent.click(await screen.findByRole('button', { name: 'Restart all' }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The PD-1 demo project is unavailable. Sync the built-in research package first.',
    )

    act(() => useAppStore.setState({ language: 'zh' }))
    expect(screen.getByRole('alert')).toHaveTextContent('PD‑1 演示项目不可用，请先同步内置研究包。')

    projectContext.projects = [{
      id: 'demo-project',
      name: 'PD-1 demo',
      source_project_key: 'PD1',
    }]
    view.rerender(<TourOverlay />)
    fireEvent.click(screen.getByRole('button', { name: '从头开始' }))
    expect(useAppStore.getState().tourState).toMatchObject({
      status: 'active',
      sectionId: 'projects',
      stepId: 'projects-welcome',
      completedSections: [],
    })
  })
})
