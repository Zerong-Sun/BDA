import { cleanup, fireEvent, screen } from '@testing-library/react'
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
    })
    server.use(
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

  it('clears authentication and project-scoped browser state while preserving preferences', () => {
    sessionStorage.setItem('bda_token', 'token')
    sessionStorage.setItem(
      'bda_user',
      JSON.stringify({ username: 'test_user', display_name: 'Test User' }),
    )

    renderWithProviders(<Topbar />)

    fireEvent.click(screen.getByText('Test User'))
    fireEvent.click(screen.getByRole('menuitem', { name: '退出登录' }))

    expect(sessionStorage.getItem('bda_token')).toBeNull()
    expect(sessionStorage.getItem('bda_user')).toBeNull()
    expect(useAppStore.getState().activeProjectId).toBe('')
    expect(useAppStore.getState().language).toBe('zh')
    expect(useAppStore.getState().copilotOpen).toBe(false)
    expect(window.location.hash).toContain('/login')
  })

  it('renders mobile-accessible primary navigation links', async () => {
    useAppStore.setState({ language: 'en' })

    renderWithProviders(<Topbar />)

    const mobileNav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(mobileNav).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Research' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Workflow' }).length).toBeGreaterThan(0)
    expect(await screen.findByRole('button', { name: 'Manage project' })).toBeInTheDocument()
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
})
