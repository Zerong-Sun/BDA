import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { BotsPage } from './Bots'

vi.mock('../features/copilot/Room', () => ({ Room: () => <div>Research room</div> }))
vi.mock('../features/copilot/BotRoster', () => ({ BotRoster: () => null }))
vi.mock('../features/copilot/CopilotSettings', () => ({ CopilotSettings: () => null }))
vi.mock('../features/copilot/CopilotChain', () => ({ CopilotChain: () => null }))
vi.mock('../features/copilot/ProceduralSkills', () => ({ ProceduralSkillCatalog: () => null, ProceduralSkillSelector: () => null }))
vi.mock('../features/projects/ProjectBriefPanel', () => ({ ProjectBriefPanel: () => null }))
vi.mock('../lib/hooks/useProjectAccess', () => ({ useProjectAccess: () => ({ data: { permissions: { write: true } } }), managesProject: () => true }))

const project = { id: 'project-task', organization_id: 'org', name: 'Research project', project_type: 'design', status: 'active', owner_id: 'user', summary: '', primary_target_id: null, version: 1, created_at: '', updated_at: '' }
const roster = [{ id: 'researcher', title: 'Researcher', title_zh: '研究员', phase: 1, stance: 'produce', summary: 'Read evidence', charter: '', capabilities: [], handoff: [], reviews: [], directs: [], reviewed_by: [], triggers: ['literature'], task_services: ['literature'], task_write_tools: { literature: ['start_literature_search'] }, absorbs: [] }]
const incoming = 'Research this project and prepare cited notes.'
let posts = 0

function taskLink(extra: Record<string, string> = {}) {
  return `#/bots?${new URLSearchParams({ project: project.id, view: 'tasks', service: 'literature', draft: incoming, draft_project: project.id, from: 'references', ...extra })}`
}

beforeEach(() => {
  posts = 0
  sessionStorage.clear()
  useAppStore.setState({ language: 'en', appMode: 'application', activeProjectId: '', copilotSessions: {}, copilotTaskDrafts: {}, copilotDraft: '' })
  window.location.hash = taskLink()
  server.use(
    http.get('/api/v2/projects', () => HttpResponse.json({ items: [project], next_cursor: null })),
    http.get('/api/v2/copilot/bots', () => HttpResponse.json(roster)),
    http.get('/api/v2/copilot/task-services', () => HttpResponse.json([{ id: 'literature', title: 'Research evidence', title_zh: '调研证据', deliverable: 'Cited notes', deliverable_zh: '引用笔记', capabilities: [], write_tools: ['start_literature_search'], steps: [] }])),
    http.get('/api/v2/copilot/projects/:projectId/task-readiness', () => HttpResponse.json({ model: 'test-model', checks: {}, eligible_services: ['literature'] })),
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [], next_cursor: null })),
    http.post('/api/v2/copilot/agent-runs', () => { posts++; return HttpResponse.json({}, { status: 500 }) }),
  )
})
afterEach(cleanup)

describe('unified task entry from research', () => {
  it('prepares the URL draft with no authorized writes and no automatic run', async () => {
    renderWithProviders(<BotsPage />)
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Task goal' })).toHaveValue(incoming))
    expect(useAppStore.getState().copilotTaskDrafts[project.id]).toMatchObject({ goal: incoming, service: 'literature', preview: true, writes: [] })
    expect(await screen.findByRole('button', { name: 'Start this plan' })).toBeEnabled()
    expect(screen.getByRole('checkbox', { name: 'Allow external literature search and ingestion' })).not.toBeChecked()
    expect(screen.getByRole('link', { name: 'Back to research materials' })).toHaveAttribute('href', '#/research?project=project-task&tab=references')
    expect(screen.queryByRole('link', { name: 'Saved discussion reports' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Project background' })).toHaveAttribute('aria-expanded', 'false')
    expect(window.location.hash).not.toContain('draft=')
    expect(posts).toBe(0)
  })

  it.each(['Keep current draft', 'Use literature draft'])('preserves the existing draft until the user chooses: %s', async (action) => {
    const existing = { goal: 'My unfinished plan', bot: 'planner', service: 'planning', preview: false, writes: ['saved-permission'], maxTurns: 12, maxCost: '25' }
    useAppStore.setState({ copilotTaskDrafts: { [project.id]: existing } })
    renderWithProviders(<BotsPage />)
    await screen.findByRole('region', { name: 'Incoming literature task draft' })
    expect(useAppStore.getState().copilotTaskDrafts[project.id]).toEqual(existing)
    fireEvent.click(screen.getByRole('button', { name: action }))
    if (action === 'Keep current draft') {
      expect(useAppStore.getState().copilotTaskDrafts[project.id]).toEqual(existing)
      expect(window.location.hash).not.toContain('service=')
    } else {
      expect(useAppStore.getState().copilotTaskDrafts[project.id]).toMatchObject({ goal: incoming, service: 'literature', writes: [] })
    }
    expect(screen.queryByRole('region', { name: 'Incoming literature task draft' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to research materials' })).toHaveAttribute('href', '#/research?project=project-task&tab=references')
    expect(posts).toBe(0)
  })

  it('does not apply a task draft to a different selected project', async () => {
    window.location.hash = taskLink({ draft_project: 'different-project' })
    renderWithProviders(<BotsPage />)
    expect(await screen.findByRole('textbox', { name: 'Task goal' })).toHaveValue('')
    expect(useAppStore.getState().copilotTaskDrafts[project.id]).toBeUndefined()
    expect(posts).toBe(0)
  })

  it('keeps task entry unavailable without a valid project', async () => {
    server.use(http.get('/api/v2/projects', () => HttpResponse.json({ items: [], next_cursor: null })))
    renderWithProviders(<BotsPage />)
    expect(await screen.findByRole('link', { name: 'Browse projects' })).toBeVisible()
    expect(screen.queryByRole('textbox', { name: 'Task goal' })).not.toBeInTheDocument()
    expect(useAppStore.getState().copilotTaskDrafts).toEqual({})
    expect(posts).toBe(0)
  })
})
