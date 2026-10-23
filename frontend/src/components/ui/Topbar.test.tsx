import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { Topbar } from './Topbar'
import { WorkspaceNavigation } from './WorkspaceNavigation'

describe('Topbar logout', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    window.location.hash = '/experiments?project=proj_live'
    useAppStore.setState({
      activeProjectId: 'proj_live',
      language: 'zh',
      copilotOpen: false,
      settingsOpen: false,
      activityOpen: false,
      tourMenuOpen: false,
    })
    server.use(
      http.get('/api/v2/operations', () => HttpResponse.json({ items: [], next_cursor: null })),
      http.get('/api/v2/projects', () =>
        HttpResponse.json({
            items: [
              {
                id: 'proj_live',
                organization_id: 'org_test',
                name: 'Live Project',
                project_type: 'protein_design',
                status: 'active',
                owner_id: 'user_test',
                summary: 'Still available',
                primary_target_id: null,
                version: 1,
                created_at: '2026-07-01T00:00:00Z',
                updated_at: '2026-07-01T00:00:00Z',
              },
            ],
            next_cursor: null,
        }),
      ),
      http.get('/api/v2/health/ready', () =>
        HttpResponse.json({
          status: 'ok',
          service: 'bda-api',
          checks: {},
        }),
      ),
    )
  })

  afterEach(cleanup)

  it('shows the project name in the closed selector instead of its ID', async () => {
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    await waitFor(() => expect(screen.getByRole('combobox', { name: '选择项目' })).toHaveTextContent('Live Project'))
  })

  it('clears authentication and project-scoped browser state while preserving preferences', async () => {
    sessionStorage.setItem('bda_token', 'token')
    sessionStorage.setItem(
      'bda_user',
      JSON.stringify({ username: 'test_user', display_name: 'Test User' }),
    )

    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)

    fireEvent.click(screen.getByText('Test User'))
    fireEvent.click(screen.getByRole('menuitem', { name: '退出登录' }))

    await waitFor(() => expect(sessionStorage.getItem('bda_token')).toBeNull())
    expect(sessionStorage.getItem('bda_user')).toBeNull()
    expect(useAppStore.getState().activeProjectId).toBe('')
    expect(useAppStore.getState().language).toBe('zh')
    expect(useAppStore.getState().copilotOpen).toBe(false)
    expect(window.location.hash).toContain('/login')
  })

  it('shows the active project name before the dropdown has been opened', async () => {
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    const selector = await screen.findByRole('combobox')
    await waitFor(() => expect(selector).toHaveTextContent('Live Project'))
    expect(selector).not.toHaveTextContent('proj_live')
  })

  it('keeps navigation and the compact page menu reachable', async () => {
    useAppStore.setState({ language: 'en' })

    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)

    const mobileNav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(mobileNav).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Project results' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Workflow' }).length).toBeGreaterThan(0)
    expect(await screen.findByRole('button', { name: 'Manage project' })).toBeInTheDocument()
  })

  it('groups primary pages and supporting workbenches in one navigator', async () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    const workspace = screen.getByRole('group', { name: 'Workspace' })
    await waitFor(() => expect(within(workspace).getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '#/workflow?project=proj_live'))
    expect(within(workspace).getAllByRole('link').map((link) => link.textContent)).toEqual(['Projects', 'Project results', 'Research team', 'Workflow', 'Review queue'])
    expect(screen.getByRole('group', { name: 'Platform' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Lab tools' })).toHaveAttribute('href', '#/tools?project=proj_live')
  })

  it('retains the current workflow and clears workflow-only state when changing workbenches', async () => {
    window.location.hash = '/workflow?project=proj_live&run=run-a&node=node-b&resource=scripts'
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    const workflow = screen.getByRole('link', { name: '工作流' })
    await waitFor(() => expect(workflow).toHaveAttribute('href', '#/workflow?project=proj_live&run=run-a&node=node-b&resource=scripts'))
    expect(workflow).toHaveAttribute('aria-current', 'page')
    fireEvent.click(screen.getByRole('button', { name: '切换页面' }))
    const tools = screen.getByRole('menuitem', { name: '实验工具' })
    expect(tools).toHaveAttribute('href', '#/tools?project=proj_live')
    fireEvent.click(tools)
    await waitFor(() => expect(window.location.hash).toBe('#/tools?project=proj_live'))
  })

  it('exposes user actions through menu semantics', () => {
    useAppStore.setState({ language: 'en' })
    sessionStorage.setItem(
      'bda_user',
      JSON.stringify({ username: 'test_user', display_name: 'Test User' }),
    )

    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    fireEvent.click(screen.getByText('Test User'))

    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /log\s*out/i })).toBeInTheDocument()
  })

  it('keeps settings reachable from the compact utility menu', () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)

    fireEvent.click(screen.getByRole('button', { name: 'More workspace actions' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Application settings' }))

    expect(useAppStore.getState().settingsOpen).toBe(true)
  })

  it('opens the assistant directly without using the compact utilities menu', () => {
    useAppStore.setState({ language: 'en', copilotOpen: false })
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    const trigger = screen.getByRole('button', { name: 'Open Copilot' })
    expect(trigger.closest('.science-desktop-utilities')).toBeNull()
    fireEvent.click(trigger)
    expect(useAppStore.getState().copilotOpen).toBe(true)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  it('has one lab-tools route, grouped workbenches and a single help entry for tours and FAQ', async () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<><Topbar /><WorkspaceNavigation /></>)
    await screen.findByRole('combobox', { name: 'Select project' })
    const navigation = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(navigation).getAllByRole('link', { name: 'Lab tools' })).toHaveLength(1)
    expect(screen.queryByRole('link', { name: 'Toolbox' })).not.toBeInTheDocument()
    expect(within(navigation).queryByRole('link', { name: /FAQ|Timeline/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Switch page' }))
    await waitFor(() => expect(within(screen.getByRole('menu')).getByText('Computational design')).toBeVisible())
    expect(within(screen.getByRole('menu')).getByText('Experimental learning')).toBeVisible()
    expect(within(screen.getByRole('menu')).getByText('Platform')).toBeVisible()
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Open interface tour' })).not.toBeInTheDocument()
    const help = screen.getByRole('button', { name: 'Help' })
    expect(help).toHaveAttribute('data-tour-id', 'tour-help')
    fireEvent.click(help)
    expect(screen.getByRole('menuitem', { name: 'FAQ' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('menuitem', { name: 'Interface tour' }))
    await waitFor(() => expect(useAppStore.getState().tourMenuOpen).toBe(true))
  })
})
