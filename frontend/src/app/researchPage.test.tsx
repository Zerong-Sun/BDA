import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { en, zh } from '../lib/i18n'
import { RESEARCH_TABS, type ResearchTab } from '../features/research/researchUi'
import { ResearchPage } from './Research'

vi.mock('../features/research/ResearchWorkspacePanel', () => ({
  ResearchWorkspacePanel: ({ view }: { view: ResearchTab }) => (
    <div data-testid="research-workspace-view">{view}</div>
  ),
}))

vi.mock('../components/ui/NextStep', () => ({
  NextStep: () => <div data-testid="next-step" />,
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
  primary_target_id: null,
  version: 1,
  created_at: '2026-07-21T00:00:00Z',
  updated_at: '2026-07-21T00:00:00Z',
}

type WorkspaceLabels = {
  research: {
    workspace: {
      tabEvidence: string
      tabReferences: string
      tabStructures: string
      tabData: string
      tabMethods: string
      tabTimeline: string
    }
    goals: { title: string }
  }
}

function tabLabel(bundle: WorkspaceLabels, tab: ResearchTab): string {
  const workspace = bundle.research.workspace
  return {
    // The goal tree has its own copy block rather than a workspace tab label: it is a
    // panel of its own, not one of the workspace views.
    goals: bundle.research.goals.title,
    evidence: workspace.tabEvidence,
    references: workspace.tabReferences,
    structures: workspace.tabStructures,
    data: workspace.tabData,
    methods: workspace.tabMethods,
    timeline: workspace.tabTimeline,
  }[tab]
}

function installHandlers() {
  server.use(
    http.get('/api/v2/projects', () => HttpResponse.json({ items: [project], next_cursor: null })),
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

  it('renders each workspace tab exactly once, with no nested sub-navigation', () => {
    renderWithProviders(<ResearchPage />)

    expect(screen.getAllByRole('tablist', { name: en.research.page.tabsLabel })).toHaveLength(1)
    for (const tab of RESEARCH_TABS) {
      expect(within(nav()).getAllByRole('tab', { name: tabLabel(en, tab) })).toHaveLength(1)
    }
    expect(within(nav()).getAllByRole('tab')).toHaveLength(RESEARCH_TABS.length)
  })

  it('exposes the URL-driven workspace navigation through registry tabs', () => {
    renderWithProviders(<ResearchPage />)

    expect(screen.getByRole('tablist', { name: en.research.page.tabsLabel })).toHaveAttribute(
      'data-slot',
      'tabs-list',
    )
    expect(screen.getByRole('tab', { name: tabLabel(en, 'evidence') })).toHaveAttribute(
      'data-slot',
      'tabs-trigger',
    )
  })

  it('associates one dynamic tabpanel with the active tab and preserves keyboard focus navigation', async () => {
    renderWithProviders(<ResearchPage />)

    const evidenceTab = screen.getByRole('tab', { name: tabLabel(en, 'evidence') })
    await screen.findByTestId('research-workspace-view')
    const panel = screen.getByRole('tabpanel')
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1)
    expect(panel).toHaveAttribute('aria-labelledby', evidenceTab.id)
    expect(within(panel).getByTestId('research-workspace-view')).toHaveTextContent('evidence')

    evidenceTab.focus()
    fireEvent.keyDown(evidenceTab, { key: 'ArrowRight' })

    const referencesTab = screen.getByRole('tab', { name: tabLabel(en, 'references') })
    await waitFor(() => expect(referencesTab).toHaveFocus())
    fireEvent.click(referencesTab)
    await waitFor(() => expect(referencesTab).toHaveAttribute('aria-selected', 'true'))
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1)
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', referencesTab.id)
    expect(within(screen.getByRole('tabpanel')).getByTestId('research-workspace-view'))
      .toHaveTextContent('references')
    expect(window.location.hash).toContain('tab=references')
  })

  it('defaults to evidence and marks it as current', () => {
    renderWithProviders(<ResearchPage />)

    expect(within(nav()).getByRole('tab', { name: tabLabel(en, 'evidence') })).toHaveAttribute(
      'aria-selected',
      'true',
    )
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

    expect(within(nav()).getByRole('tab', { name: tabLabel(en, expectedTab) })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })

  it('uses the language selected in settings without rendering a local language switch', () => {
    const rendered = renderWithProviders(<ResearchPage />)

    expect(screen.queryByRole('button', { name: en.shared.userMenu.chinese })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: en.shared.userMenu.english })).not.toBeInTheDocument()

    useAppStore.setState({ language: 'zh' })
    rendered.rerender(<ResearchPage />)
    expect(screen.getByRole('heading', { name: zh.research.page.title })).toBeInTheDocument()
    const zhNav = nav(zh.research.page.tabsLabel)
    for (const tab of RESEARCH_TABS) {
      expect(within(zhNav).getByRole('tab', { name: tabLabel(zh, tab) })).toBeInTheDocument()
    }
  })

  it('keeps one workspace mounted while switching its URL-driven view', async () => {
    renderWithProviders(<ResearchPage />)
    await waitFor(() => expect(screen.getByTestId('research-workspace-view')).toHaveTextContent('evidence'))

    fireEvent.click(within(nav()).getByRole('tab', { name: tabLabel(en, 'structures') }))

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
  })
})
