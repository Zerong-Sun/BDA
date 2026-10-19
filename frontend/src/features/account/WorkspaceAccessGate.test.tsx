import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/mocks/handlers'
import { invalidateAuthRequests } from '../../lib/api/client'
import { WorkspaceAccessGate } from './WorkspaceAccessGate'

const config = { deployment_kind: 'private', registration_mode: 'closed', realm: 'private', public_workspace_enabled: false }
const user = { id: 'account-one', username: 'scientist', display_name: 'Scientist', role: 'researcher' }

afterEach(() => { invalidateAuthRequests(); sessionStorage.clear(); window.location.hash = '' })
function setup() {
  server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json(config)))
  window.location.hash = '#/workflow?project=existing-project&run=existing-run'
  return renderWithProviders(<Routes><Route element={<WorkspaceAccessGate />}><Route path="/workflow" element={<h1>Workflow ready</h1>} /></Route><Route path="/login" element={<h1>Sign in</h1>} /></Routes>)
}

describe('Private workspace session restoration', () => {
  it('restores a refresh-cookie session before mounting the requested workspace', async () => {
    const refresh = vi.fn(() => HttpResponse.json({ access_token: 'restored-access', user }))
    server.use(http.post('*/api/v2/auth/refresh', refresh))
    setup()
    expect(await screen.findByRole('heading', { name: 'Workflow ready' })).toBeVisible()
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('bda_token')).toBe('restored-access')
    expect(JSON.parse(sessionStorage.getItem('bda_user')!).id).toBe(user.id)
    expect(window.location.hash).toBe('#/workflow?project=existing-project&run=existing-run')
    expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
  })

  it('tries restoration once and redirects a rejected cookie while retaining the deep link', async () => {
    const refresh = vi.fn(() => new HttpResponse(null, { status: 401 }))
    server.use(http.post('*/api/v2/auth/refresh', refresh))
    setup()
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible()
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(window.location.hash).toContain('returnTo=%2Fworkflow%3Fproject%3Dexisting-project%26run%3Dexisting-run')
    expect(sessionStorage.getItem('bda_token')).toBeNull()
  })

  it('does not refresh an existing access token on startup', async () => {
    sessionStorage.setItem('bda_token', 'existing-token')
    const refresh = vi.fn(() => HttpResponse.json({ access_token: 'unexpected', user }))
    server.use(http.post('*/api/v2/auth/refresh', refresh))
    setup()
    expect(await screen.findByRole('heading', { name: 'Workflow ready' })).toBeVisible()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('offers an explicit retry for unavailable refresh service instead of discarding the session', async () => {
    let calls = 0
    server.use(http.post('*/api/v2/auth/refresh', () => ++calls === 1 ? new HttpResponse(null, { status: 503 }) : HttpResponse.json({ access_token: 'recovered', user })))
    setup()
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
    expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'Workflow ready' })).toBeVisible()
    expect(calls).toBe(2)
  })

  it('does not switch a remembered account to a different refresh-cookie owner', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ ...user, id: 'different-account' }))
    server.use(http.post('*/api/v2/auth/refresh', () => HttpResponse.json({ access_token: 'wrong-account', user })))
    setup()
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible()
    expect(sessionStorage.getItem('bda_token')).toBeNull()
    expect(JSON.parse(sessionStorage.getItem('bda_user')!).id).toBe('different-account')
  })

  it('cannot restore an old response after the browser session was invalidated', async () => {
    let finish!: () => void
    const pending = new Promise<void>(resolve => { finish = resolve })
    const refresh = vi.fn(async () => { await pending; return HttpResponse.json({ access_token: 'late', user }) })
    server.use(http.post('*/api/v2/auth/refresh', refresh))
    setup()
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1))
    await act(async () => { invalidateAuthRequests(); finish() })
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible()
    expect(sessionStorage.getItem('bda_token')).toBeNull()
    expect(refresh).toHaveBeenCalledTimes(1)
  })
})
