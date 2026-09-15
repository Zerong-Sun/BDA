import { cleanup, fireEvent, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { CommandPalette } from './CommandPalette'

/**
 * The palette exists so that knowing where you want to go is enough to get
 * there. The tests are about the three things that would make it a liability:
 *
 * * a shortcut with no visible counterpart, which most people never discover;
 * * a fuzzy-matched list that can *act* - pressing Enter a moment early should
 *   never start a run or confirm a draft;
 * * opening it issuing requests, which turns a search box into a spinner and
 *   gives it a failure mode.
 */

afterEach(cleanup)

const PROJECT = {
  id: 'proj_pd1', organization_id: 'org', name: 'PD-1 binder', project_type: 'protein_design',
  status: 'active', owner_id: 'u', summary: '', primary_target_id: null, version: 1,
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
}

const BOT = {
  id: 'runner', title: 'Runner', title_zh: '执行与排障', phase: 3, stance: 'produce',
  summary: '', charter: '', capabilities: [], handoff: [], reviews: [], directs: [],
  reviewed_by: [], triggers: [], task_services: [], task_write_tools: {}, absorbs: [],
}

function stub() {
  useAppStore.setState({ activeProjectId: '', language: 'en' })
  server.use(
    http.get('/api/v2/projects', () => HttpResponse.json({ items: [PROJECT], next_cursor: null })),
    http.get('/api/v2/copilot/bots', () => HttpResponse.json([BOT])),
  )
}

async function openWithKeyboard() {
  stub()
  renderWithProviders(<CommandPalette />)
  fireEvent.keyDown(window, { key: 'k', metaKey: true })
  return screen.findByPlaceholderText(/Type a page, project or member/i)
}

describe('CommandPalette', () => {
  it('opens on the keyboard shortcut', async () => {
    expect(await openWithKeyboard()).toBeInTheDocument()
  })

  it('also opens from a visible control, so it is discoverable without the chord', async () => {
    stub()
    renderWithProviders(<CommandPalette />)

    fireEvent.click(screen.getByRole('button', { name: 'Search and jump' }))

    expect(await screen.findByPlaceholderText(/Type a page, project or member/i)).toBeInTheDocument()
  })

  it('lists pages under the names navigation uses for them', async () => {
    await openWithKeyboard()

    // The two routes whose nav wording differs from their page titles.
    expect(await screen.findByText('Decisions')).toBeInTheDocument()
    expect(screen.getByText('Research team')).toBeInTheDocument()
  })

  it('indexes the projects and the roster already loaded', async () => {
    await openWithKeyboard()

    expect(await screen.findByText('PD-1 binder')).toBeInTheDocument()
    expect(screen.getByText('Runner')).toBeInTheDocument()
  })

  it('navigates when a result is chosen', async () => {
    await openWithKeyboard()

    fireEvent.click(await screen.findByText('Research team'))

    expect(window.location.hash).toContain('/bots')
  })

  it('offers no action that spends anything', async () => {
    await openWithKeyboard()

    const forbidden = /start|run now|submit|confirm|delete|cancel|approve/i
    for (const option of screen.getAllByRole('option')) {
      expect(option.textContent ?? '').not.toMatch(forbidden)
    }
  })

  it('closes on a second press of the shortcut', async () => {
    await openWithKeyboard()

    fireEvent.keyDown(window, { key: 'k', metaKey: true })

    expect(screen.queryByPlaceholderText(/Type a page, project or member/i)).not.toBeInTheDocument()
  })
})
