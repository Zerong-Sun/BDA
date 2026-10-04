import { beforeEach, describe, expect, it } from 'vitest'
import { initialTourState, useAppStore } from './appStore'

describe('tour state', () => {
  beforeEach(() => {
    localStorage.clear()
    useAppStore.setState({ appMode: 'application', tourState: initialTourState, tourMenuOpen: false })
  })

  it('starts, advances, goes back, and pauses a chapter', () => {
    const store = useAppStore.getState()
    store.startTour('projects')
    expect(useAppStore.getState().appMode).toBe('demo')
    expect(useAppStore.getState().tourState).toMatchObject({ status: 'active', sectionId: 'projects', stepId: 'projects-welcome' })
    useAppStore.getState().advanceTour()
    expect(useAppStore.getState().tourState.stepId).toBe('project-selector')
    useAppStore.getState().backTour()
    expect(useAppStore.getState().tourState.stepId).toBe('projects-welcome')
    useAppStore.getState().skipTour()
    expect(useAppStore.getState()).toMatchObject({ tourState: { status: 'paused' }, tourMenuOpen: true })
  })

  it('marks a completed chapter and opens the chapter menu', () => {
    useAppStore.getState().startTour('faq')
    useAppStore.getState().advanceTour()
    expect(useAppStore.getState().tourState.completedSections).toContain('faq')
    expect(useAppStore.getState().tourMenuOpen).toBe(true)
  })

  it('restarts from the first project step and clears completion', () => {
    useAppStore.setState({ tourState: { ...initialTourState, status: 'completed', completedSections: ['faq'] } })
    useAppStore.getState().restartTour()
    expect(useAppStore.getState().tourState).toMatchObject({ status: 'active', sectionId: 'projects', stepId: 'projects-welcome', completedSections: [] })
    expect(useAppStore.getState().appMode).toBe('demo')
  })

  it('restores demo mode with an active persisted tour without changing its step', async () => {
    localStorage.setItem('bda-app-store', JSON.stringify({ state: {
      tourState: { ...initialTourState, status: 'active', sectionId: 'workflow', stepId: 'workflow-inspector' },
    }, version: 0 }))
    await useAppStore.persist.rehydrate()
    expect(useAppStore.getState()).toMatchObject({ appMode: 'demo', tourState: {
      status: 'active', sectionId: 'workflow', stepId: 'workflow-inspector',
    } })
  })

  it.each(['idle', 'paused', 'completed'] as const)('leaves application mode alone when restoring a %s tour', async (status) => {
    localStorage.setItem('bda-app-store', JSON.stringify({ state: { tourState: { ...initialTourState, status } }, version: 0 }))
    await useAppStore.persist.rehydrate()
    expect(useAppStore.getState().appMode).toBe('application')
    expect(useAppStore.getState().tourState.status).toBe(status)
  })

  it('pauses an active tour when the user explicitly enters application mode, and resumes in demo', () => {
    useAppStore.getState().startTour('workflow')
    useAppStore.getState().advanceTour()
    useAppStore.getState().setAppMode('application')
    expect(useAppStore.getState()).toMatchObject({ appMode: 'application', tourMenuOpen: false,
      tourState: { status: 'paused', stepId: 'workflow-canvas' } })
    useAppStore.getState().resumeTour()
    expect(useAppStore.getState()).toMatchObject({ appMode: 'demo',
      tourState: { status: 'active', stepId: 'workflow-canvas' } })
  })

  it('preserves progress but pauses an active tour on sign out', () => {
    useAppStore.getState().startTour('workflow')
    useAppStore.getState().advanceTour()
    useAppStore.getState().resetAuthenticatedState()
    expect(useAppStore.getState()).toMatchObject({ appMode: 'application',
      tourState: { status: 'paused', stepId: 'workflow-canvas' } })
  })
})
