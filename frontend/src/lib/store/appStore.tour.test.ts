import { beforeEach, describe, expect, it } from 'vitest'
import { initialTourState, useAppStore } from './appStore'

describe('tour state', () => {
  beforeEach(() => {
    useAppStore.setState({ tourState: initialTourState, tourMenuOpen: false })
  })

  it('starts, advances, goes back, and pauses a chapter', () => {
    const store = useAppStore.getState()
    store.startTour('projects')
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
  })
})
