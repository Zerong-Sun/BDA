import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { Topbar } from './Topbar'

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
    renderWithProviders(<Topbar />)
    await waitFor(() => expect(screen.getByRole('combobox', { name: '选择项目' })).toHaveTextContent('Live Project'))
  })

  it('clears authentication and project-scoped browser state while preserving preferences', async () => {
    sessionStorage.setItem('bda_token', 'token')
    sessionStorage.setItem(
      'bda_user',
      JSON.stringify({ username: 'test_user', display_name: 'Test User' }),
    )

    renderWithProviders(<Topbar />)

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
    renderWithProviders(<Topbar />)
    const selector = await screen.findByRole('combobox')
    await waitFor(() => expect(selector).toHaveTextContent('Live Project'))
    expect(selector).not.toHaveTextContent('proj_live')
  })

  it('renders mobile-accessible primary navigation links', async () => {
    useAppStore.setState({ language: 'en' })

    renderWithProviders(<Topbar />)

    const mobileNav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(mobileNav).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Project results' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Workflow' }).length).toBeGreaterThan(0)
    expect(await screen.findByRole('button', { name: 'Manage project' })).toBeInTheDocument()
  })

  it('orders project navigation and keeps supporting resources in the menu', async () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<Topbar />)
    const nav = screen.getByRole('navigation')
    await waitFor(() => expect(within(nav).getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '#/workflow?project=proj_live'))
    expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['Projects', 'Project results', 'Research team', 'Workflow', 'Review queue'])
    fireEvent.click(screen.getByRole('button', { name: 'Workbenches' }))
    expect(screen.getByRole('menuitem', { name: 'Models & plugins' })).toHaveAttribute('href', '#/workflow?project=proj_live&resource=plugins')
    expect(screen.getByRole('menuitem', { name: 'Scripts' })).toHaveAttribute('href', '#/workflow?project=proj_live&resource=scripts')
  })

  it('switches resources without losing the selected workflow', async () => {
    window.location.hash = '/workflow?project=proj_live&run=run-a&node=node-b&resource=scripts'
    renderWithProviders(<Topbar />)
    expect(screen.getByRole('link', { name: '工作流' })).toHaveAttribute('aria-current', 'page')
    fireEvent.click(screen.getByRole('button', { name: '工作台' }))
    expect(screen.getByRole('menuitem', { name: '脚本' })).toHaveAttribute('aria-current', 'page')
    const plugins = screen.getByRole('menuitem', { name: '模型插件' })
    expect(plugins).toHaveAttribute('href', '#/workflow?project=proj_live&run=run-a&node=node-b&resource=plugins')
    fireEvent.click(plugins)
    await waitFor(() => expect(window.location.hash).toContain('run=run-a&node=node-b&resource=plugins'))
  })

  it('exposes user actions through menu semantics', () => {
    useAppStore.setState({ language: 'en' })
    sessionStorage.setItem(
      'bda_user',
      JSON.stringify({ username: 'test_user', display_name: 'Test User' }),
    )

    renderWithProviders(<Topbar />)
    fireEvent.click(screen.getByText('Test User'))

    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /log\s*out/i })).toBeInTheDocument()
  })

  it('keeps settings reachable from the compact utility menu', () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<Topbar />)

    fireEvent.click(screen.getByRole('button', { name: 'More workspace actions' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Application settings' }))

    expect(useAppStore.getState().settingsOpen).toBe(true)
  })

  it('has one lab-tools route, grouped workbenches and a single help entry for tours and FAQ', async () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<Topbar />)
    await screen.findByRole('combobox', { name: 'Select project' })
    const navigation = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(navigation).queryByRole('link', { name: 'Lab tools' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Toolbox' })).not.toBeInTheDocument()
    expect(within(navigation).queryByRole('link', { name: /FAQ|Timeline/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Workbenches' }))
    await waitFor(() => expect(screen.getByText('Computational design')).toBeVisible())
    expect(screen.getByText('Experimental learning')).toBeVisible()
    expect(screen.getByText('Platform')).toBeVisible()
    expect(screen.getByRole('menuitem', { name: 'Lab tools' })).toBeVisible()
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
