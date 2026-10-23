import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { APP_ROUTES } from '../../lib/nav/routes'
import { WorkspaceNavigation } from './WorkspaceNavigation'

const project = {
  id: 'proj_nav', name: 'Navigation project', status: 'active', project_type: 'protein_design',
  organization_id: 'org', owner_id: 'user', summary: null, primary_target_id: null,
  version: 1, created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
}

beforeEach(() => {
  window.location.hash = '/bots/researcher?project=proj_nav'
  useAppStore.setState({ activeProjectId: project.id, language: 'en' })
  server.use(http.get('/api/v2/projects', () => HttpResponse.json({ items: [project], next_cursor: null })))
})
afterEach(cleanup)

describe('WorkspaceNavigation', () => {
  it('exposes each registered page once and marks the parent of a nested route', async () => {
    renderWithProviders(<WorkspaceNavigation />)
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    await waitFor(() => expect(within(nav).getByRole('link', { name: 'Research team' })).toHaveAttribute('href', '#/bots?project=proj_nav'))
    expect(within(nav).getAllByRole('link')).toHaveLength(APP_ROUTES.length)
    expect(within(nav).getByRole('link', { name: 'Research team' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Switch page' })).toHaveTextContent('Research team')
  })

  it('navigates from the compact menu using a real project-scoped link', async () => {
    renderWithProviders(<WorkspaceNavigation />)
    await waitFor(() => expect(screen.getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '#/workflow?project=proj_nav'))
    fireEvent.click(screen.getByRole('button', { name: 'Switch page' }))
    const menu = await screen.findByRole('menu')
    const workflow = within(menu).getByRole('menuitem', { name: 'Workflow' })
    expect(workflow).toHaveAttribute('href', '#/workflow?project=proj_nav')
    fireEvent.click(workflow)
    await waitFor(() => expect(window.location.hash).toBe('#/workflow?project=proj_nav'))
    await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Switch page' })).toHaveTextContent('Workflow')
  })

  it('keeps projectless tools reachable after a stale project is removed', async () => {
    server.use(http.get('/api/v2/projects', () => HttpResponse.json({ items: [], next_cursor: null })))
    renderWithProviders(<WorkspaceNavigation />)
    await waitFor(() => expect(screen.getByRole('link', { name: 'Lab tools' })).toHaveAttribute('href', '#/tools'))
    await waitFor(() => expect(useAppStore.getState().activeProjectId).toBe(''))
    expect(window.location.hash).not.toContain('project=')
  })
})
