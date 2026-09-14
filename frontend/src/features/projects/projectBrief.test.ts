import { beforeEach, describe, expect, it } from 'vitest'
import type { Project } from '../../lib/api/projects'
import { useAppStore } from '../../lib/store/appStore'
import { projectBrief } from './projectBrief'

const project = { id: 'public-project', name: 'PD1', summary: 'Stored objective', prompt: null, source_package_id: 'pd1-demo-v1', source_project_key: 'PD1' } as Project

describe('source-backed project briefs', () => {
  it('shows an authored public-project brief instead of masking it with package copy', () => {
    const edited = { ...project, prompt: 'Review only the sources selected by the customer.' }
    expect(projectBrief(edited, 'en')).toEqual({ source: 'project', objective: edited.prompt, questions: [], deliverables: [] })
    expect(projectBrief({ ...project, prompt: project.summary }, 'en').source).toBe('public-package')
  })
  it('presents public-package questions in both languages without claiming goal completion', () => {
    for (const language of ['en', 'zh'] as const) {
      const brief = projectBrief(project, language)
      expect(brief.source).toBe('public-package')
      expect(brief.questions).toHaveLength(3)
      expect(brief.deliverables).toHaveLength(3)
      expect(brief.objective).not.toBe(project.summary)
    }
  })

  it('never applies the public PD1 narrative to a private project with the same title or key', () => {
    expect(projectBrief({ ...project, source_package_id: 'private-package' }, 'en')).toEqual({ source: 'project', objective: 'Stored objective', questions: [], deliverables: [] })
  })

  it('keeps user-authored objectives intact and leaves missing evidence explicitly absent', () => {
    const edited = { ...project, source_package_id: null, prompt: 'My actual question\nwith constraints' }
    expect(projectBrief(edited, 'en').objective).toBe(edited.prompt)
    expect(projectBrief({ ...edited, prompt: null, summary: null }, 'en').objective).toBe('')
  })
})

describe('project-scoped Bot context', () => {
  beforeEach(() => useAppStore.setState({ activeProjectId: 'project-a', copilotDraft: 'Unsent question from A', copilotSelectedEntityIds: ['structure-a'], copilotSessions: { 'project-a': { bot: 'auditor', conversationId: 'conversation-a', messages: [] } } }))

  it('clears draft context when switching projects while retaining the saved conversation', () => {
    useAppStore.getState().setActiveProjectId('project-b')
    expect(useAppStore.getState().copilotDraft).toBe('')
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual([])
    expect(useAppStore.getState().copilotSessions['project-a'].bot).toBe('auditor')
  })

  it('keeps the selected structures and draft when navigating within a project', () => {
    useAppStore.getState().setActiveProjectId('project-a')
    expect(useAppStore.getState().copilotDraft).toBe('Unsent question from A')
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual(['structure-a'])
  })

  it('restores each project’s own unsent input and selected sources', () => {
    const state = useAppStore.getState()
    state.setCopilotSessionInput('project-a', 'Explain source A')
    state.setCopilotSelectedEntityIds(['structure-a'])
    state.setActiveProjectId('project-b')
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual([])
    expect(useAppStore.getState().copilotSessions['project-b']).toBeUndefined()
    state.setCopilotSessionInput('project-b', 'Explain source B')
    state.setCopilotSelectedEntityIds(['structure-b'])
    state.setActiveProjectId('project-a')
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual(['structure-a'])
    expect(useAppStore.getState().copilotSessions['project-a'].input).toBe('Explain source A')
    expect(useAppStore.getState().copilotSessions['project-b'].input).toBe('Explain source B')
  })

  it('removes drafts on project deletion and clears all drafts on sign out', () => {
    const state = useAppStore.getState()
    const draft = { goal: 'Review evidence', bot: null, service: null, preview: false, writes: [], maxTurns: 24, maxCost: '' }
    state.setCopilotTaskDraft('project-a', draft)
    state.setCopilotTaskDraft('project-b', draft)
    state.clearProjectState('project-a')
    expect(useAppStore.getState().copilotTaskDrafts['project-a']).toBeUndefined()
    expect(useAppStore.getState().copilotSessions['project-a']).toBeUndefined()
    expect(useAppStore.getState().copilotDraft).toBe('')
    state.resetAuthenticatedState()
    expect(useAppStore.getState().copilotTaskDrafts).toEqual({})
    expect(useAppStore.getState().copilotSessions).toEqual({})
  })

  it('does not clear another project’s sources when a previous reply finishes', () => {
    const state = useAppStore.getState()
    state.setCopilotSelectedEntityIds(['structure-a'])
    state.setActiveProjectId('project-b')
    state.setCopilotSelectedEntityIds(['structure-b'])
    state.setCopilotSelectedEntityIds([], 'project-a')
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual(['structure-b'])
    expect(useAppStore.getState().copilotSessions['project-a'].selectedEntityIds).toEqual([])
  })
})
