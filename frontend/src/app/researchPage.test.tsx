import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { en, zh } from '../lib/i18n'
import { type ResearchTab } from '../features/research/researchUi'
import { ResearchPage } from './Research'

vi.mock('../features/research/ResearchWorkspacePanel', () => ({
  ResearchWorkspacePanel: ({ view }: { view: ResearchTab }) => (
    <div data-testid="research-workspace-view">{view}</div>
  ),
}))

vi.mock('../components/ui/NextStep', () => ({
  NextStep: () => <div data-testid="next-step" />,
}))
vi.mock('../features/research/ResearchDecisionCenter', () => ({
  ResearchDecisionCenter: () => <div data-testid="decision-center" />,
}))

const project = {
  id: 'proj_research',
  name: 'Research redesign project',
  legacy_id: null,
  organization_id: 'org_test',
  project_type: 'binder_design',
  status: 'active',
  owner_id: 'user_admin',
  summary: 'Verify the research workspace.',
  prompt: 'A confirmed research brief.',
  primary_target_id: null,
  version: 1,
  created_at: '2026-07-21T00:00:00Z',
  updated_at: '2026-07-21T00:00:00Z',
}

const englishGroups = ['Goals & questions', 'Literature & evidence', 'Experiment plan', 'Decision record']
const chineseGroups = ['目标与问题', '文献与证据', '实验方案', '决策记录']

vi.mock('../features/research/ResearchGoalsPanel', () => ({
  ResearchGoalsPanel: () => <div data-testid="research-goals-view" />,
}))
vi.mock('../features/timeline/ProjectTimeline', () => ({
  ProjectTimeline: ({ hasPrompt }: { hasPrompt: boolean }) => <div data-testid="research-timeline-view">{String(hasPrompt)}</div>,
}))

function installHandlers() {
  server.use(
    http.get('/api/v2/projects', () => HttpResponse.json({ items: [project], next_cursor: null })),
    http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({ project: { id: project.id }, review_document: null })),
    http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [], next_cursor: null })),
  )
}

function nav(label: string = en.research.page.tabsLabel) {
  return screen.getByRole('tablist', { name: label })
}

describe('ResearchPage', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    window.location.hash = '/research?project=proj_research'
    installHandlers()
  })

  afterEach(() => {
    cleanup()
    useAppStore.setState({ language: 'en' })
  })

  it('renders the project brief at the destination used by research team links', async () => {
    window.location.hash = '/research?project=proj_research&tab=goals&brief=1'
    renderWithProviders(<ResearchPage />)
    const brief = await screen.findByRole('region', { name: 'Project brief' })
    expect(within(brief).getByText('A confirmed research brief.')).toBeInTheDocument()
    expect(screen.getAllByRole('region', { name: 'Project brief' })).toHaveLength(1)
  })

  it('prioritizes the saved research summary for archived projects and folds planning controls', async () => {
    server.use(
      http.get('/api/v2/projects', () => HttpResponse.json({ items: [{ ...project, status: 'archived' }], next_cursor: null })),
      http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({
        project: { id: project.id },
        review_document: { id: 'saved-report', title: { en: 'Saved study' }, content: { en: '## Research objective\nThe historical research question.\n## Findings\nThe historical result.' }, status: 'accepted', version: 1 },
      })),
    )
    renderWithProviders(<ResearchPage />)
    await waitFor(() => expect(screen.getByText('The historical research question.')).toBeVisible())
    expect(screen.getByText('The historical result.')).toBeVisible()
    expect(within(nav()).getByRole('tab', { name: 'Results & reports' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByTestId('decision-center')).not.toBeInTheDocument()
    expect(screen.queryByTestId('next-step')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Structured questions and decision definitions' }))
    expect(await screen.findByTestId('decision-center')).toBeVisible()
  })

  it('defaults to goals and presents four stages with accessible controls', () => {
    renderWithProviders(<ResearchPage />)
    expect(within(nav()).getAllByRole('tab')).toHaveLength(4)
    for (const label of englishGroups) {
      expect(within(nav()).getByRole('tab', { name: label })).toHaveAttribute('data-slot', 'tabs-trigger')
    }
    expect(within(nav()).getByRole('tab', { name: englishGroups[0] })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByRole('navigation', { name: 'Evidence categories' })).not.toBeInTheDocument()
  })

  it('shows saved outcomes for an active project without treating it as completed or hiding its goals', async () => {
    server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({
      project: { id: project.id },
      review_document: { id: 'saved-report', title: { en: 'Stage report' }, content: { en: '## Research objective\nAn ongoing question.\n## Results\nA recorded stage result.' }, status: 'accepted', version: 1 },
    })))
    renderWithProviders(<ResearchPage />)
    await waitFor(() => expect(screen.getByText('A recorded stage result.')).toBeVisible())
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Project results, reports & review')
    expect(within(nav()).getByRole('tab', { name: 'Results & reports' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByText('Completed project · saved research record')).not.toBeInTheDocument()
    expect(screen.getByTestId('next-step')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Manage questions and goal tree' }))
    expect(await screen.findByTestId('research-goals-view')).toBeVisible()
  })

  it('keeps report load failures visible while allowing access to existing goals', async () => {
    server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({ detail: 'unavailable' }, { status: 503 })))
    renderWithProviders(<ResearchPage />)
    expect(await screen.findByText(/The project report could not be loaded/)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Manage questions and goal tree' }))
    expect(await screen.findByTestId('research-goals-view')).toBeVisible()
  })

  it('supports keyboard navigation between stages and evidence subcategories', async () => {
    renderWithProviders(<ResearchPage />)
    const goals = within(nav()).getByRole('tab', { name: englishGroups[0] })
    const evidence = within(nav()).getByRole('tab', { name: englishGroups[1] })
    goals.focus()
    fireEvent.keyDown(goals, { key: 'ArrowRight' })
    await waitFor(() => expect(evidence).toHaveFocus())
    fireEvent.click(evidence)
    await screen.findByTestId('research-workspace-view')
    const panel = screen.getByRole('tabpanel')
    expect(panel).toHaveAttribute('aria-labelledby', evidence.id)
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Evidence categories' })).getByRole('button', { name: en.research.workspace.tabReferences }))
    expect(within(panel).getByTestId('research-workspace-view')).toHaveTextContent('references')
    expect(window.location.hash).toContain('tab=references')
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1)
  })

  it('passes the confirmed brief into the decision record', async () => {
    window.location.hash = '/research?project=proj_research&tab=timeline'
    renderWithProviders(<ResearchPage />)
    await waitFor(() => expect(screen.getByTestId('research-timeline-view')).toHaveTextContent('true'))
  })

  it('preserves the project and browser history when changing research tabs', async () => {
    window.location.hash = '/research?project=proj_research&tab=methods'
    renderWithProviders(<ResearchPage />)
    await screen.findByTestId('research-workspace-view')
    fireEvent.click(within(nav()).getByRole('tab', { name: 'Decision record' }))
    expect(window.location.hash).toContain('project=proj_research')
    expect(window.location.hash).toContain('tab=timeline')
    window.history.back()
    await waitFor(() => expect(window.location.hash).toContain('tab=methods'))
    expect(within(nav()).getByRole('tab', { name: 'Experiment plan' })).toHaveAttribute('aria-selected', 'true')
  })

  it('shows one research title and keeps goal management explicitly expandable', async () => {
    renderWithProviders(<ResearchPage />)
    await screen.findByTestId('decision-center')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(en.research.page.title)
    expect(screen.queryByText(project.name)).not.toBeInTheDocument()
    expect(screen.queryByText(project.prompt)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Research team' })).not.toBeInTheDocument()
    const manage = screen.getByRole('button', { name: 'Manage questions and goal tree' })
    expect(manage).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('research-goals-view')).not.toBeInTheDocument()
    fireEvent.click(manage)
    expect(await screen.findByTestId('research-goals-view')).toBeVisible()
  })

  it('opens literature research as a project-scoped draft in the unified task workspace', async () => {
    window.location.hash = '/research?project=proj_research&tab=references'
    renderWithProviders(<ResearchPage />)
    const link = await screen.findByRole('link', { name: 'Prepare AI literature task' })
    const url = new URL(link.getAttribute('href')!.slice(1), 'https://local.test')
    expect(url.pathname).toBe('/bots')
    expect(Object.fromEntries(url.searchParams)).toMatchObject({ project: project.id, draft_project: project.id, service: 'literature', view: 'tasks', from: 'references' })
    expect(url.searchParams.get('draft')).toContain('Prepare drafts only')
    expect(screen.queryByRole('textbox', { name: 'Task goal' })).not.toBeInTheDocument()
  })

  it.each([
    ['atlas', 'evidence'],
    ['review', 'evidence'],
    ['literature', 'references'],
    ['target', 'structures'],
    ['library', 'data'],
    ['knowledge', 'data'],
  ] satisfies Array<[string, ResearchTab]>)('migrates the legacy ?tab=%s deep link', (legacyTab, expectedTab) => {
    window.location.hash = `/research?project=proj_research&tab=${legacyTab}`
    renderWithProviders(<ResearchPage />)

    expect(within(nav()).getByRole('tab', { name: englishGroups[1] })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(window.location.hash).toContain(`tab=${expectedTab}`)
  })

  it('uses the language selected in settings without rendering a local language switch', () => {
    const rendered = renderWithProviders(<ResearchPage />)

    expect(screen.queryByRole('button', { name: en.shared.userMenu.chinese })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: en.shared.userMenu.english })).not.toBeInTheDocument()

    useAppStore.setState({ language: 'zh' })
    rendered.rerender(<ResearchPage />)
    expect(screen.getByRole('heading', { name: zh.research.page.title })).toBeInTheDocument()
    const zhNav = nav(zh.research.page.tabsLabel)
    for (const label of chineseGroups) {
      expect(within(zhNav).getByRole('tab', { name: label })).toBeInTheDocument()
    }
  })

  it('keeps one workspace mounted while switching its URL-driven view', async () => {
    window.location.hash = '/research?project=proj_research&tab=evidence'
    renderWithProviders(<ResearchPage />)
    await waitFor(() => expect(screen.getByTestId('research-workspace-view')).toHaveTextContent('evidence'))

    fireEvent.click(screen.getByRole('button', { name: en.research.workspace.tabStructures }))

    expect(screen.getByTestId('research-workspace-view')).toHaveTextContent('structures')
    expect(screen.getAllByTestId('research-workspace-view')).toHaveLength(1)
    expect(window.location.hash).toContain('tab=structures')
  })
})

describe('ResearchPage without a project', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    window.location.hash = '/research'
    server.use(http.get('/api/v2/projects', () => HttpResponse.json({ items: [], next_cursor: null })))
  })

  afterEach(() => cleanup())

  it('shows the project notice once and mounts no workspace', () => {
    renderWithProviders(<ResearchPage />)

    expect(screen.getAllByText(en.research.projectNotice)).toHaveLength(1)
    expect(screen.queryByTestId('research-workspace-view')).toBeNull()
    expect(screen.queryByRole('link', { name: 'Prepare AI literature task' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Manage questions and goal tree' })).not.toBeInTheDocument()
  })
})
