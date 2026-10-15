import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from '../test/renderWithProviders'
import { server } from '../test/mocks/handlers'
import { useAppStore } from '../lib/store/appStore'
import { LoginPage, RegisterPage, ResetPasswordPage } from './Login'
import { AccountPage } from './Account'
import { portalLoginUrl, portalUrl, safeReturnTo } from '../lib/auth/account'

const config = { deployment_kind: 'private', registration_mode: 'open', realm: 'private', public_portal_url: 'http://localhost:5176', private_portal_url: 'http://localhost:5177' }
const user = { id: 'user-test', username: 'alice', display_name: 'Alice', role: 'researcher', version: 4, has_password: true }
function field(name: string, value: string) { fireEvent.change(screen.getByLabelText(name, { exact: true }), { target: { value } }) }
function passwords() { field('Password', 'Example-pass-123'); field('Confirm password', 'Example-pass-123') }
afterEach(() => { sessionStorage.clear(); window.location.hash = ''; useAppStore.getState().setLanguage('en') })

describe('account access', () => {
  it('registers a Private account without client-supplied role or organization', async () => {
    let body: unknown
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json(config)), http.post('*/api/v2/auth/register', async ({ request }) => { body = await request.json(); return HttpResponse.json({ access_token: 'new-access', user }) }))
    renderWithProviders(<RegisterPage />)
    await screen.findByRole('link', { name: /Private workspace/ })
    field('Username', 'alice'); field('Display name', 'Alice'); passwords()
    fireEvent.submit(document.querySelector('form')!)
    await waitFor(() => expect(sessionStorage.getItem('bda_token')).toBe('new-access'))
    expect(body).toEqual({ username: 'alice', display_name: 'Alice', password: 'Example-pass-123' })
    expect(window.location.hash).toBe('#/projects')
  })

  it('requires a Private invitation and rejects mismatched passwords before sending', async () => {
    const submit = vi.fn(() => HttpResponse.json({}))
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({ ...config, deployment_kind: 'private', registration_mode: 'invite' })), http.post('*/api/v2/auth/register', submit))
    renderWithProviders(<RegisterPage />)
    await screen.findByLabelText('Invitation code')
    field('Username', 'alice'); field('Display name', 'Alice'); passwords(); field('Invitation code', 'code')
    field('Confirm password', 'different-123')
    fireEvent.submit(document.querySelector('form')!)
    expect(await screen.findByText('The passwords do not match.')).toBeVisible()
    expect(submit).not.toHaveBeenCalled()
  })

  it('lets a Private self-service user choose an existing team invitation', async () => {
    let body: unknown
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json(config)), http.post('*/api/v2/auth/register', async ({ request }) => { body = await request.json(); return HttpResponse.json({ access_token: 'invited-access', user }) }))
    renderWithProviders(<RegisterPage />)
    fireEvent.click(await screen.findByRole('checkbox', { name: 'I have an invitation to an existing team' }))
    field('Username', 'alice'); field('Display name', 'Alice'); passwords(); field('Invitation code', 'synthetic-invitation')
    fireEvent.submit(document.querySelector('form')!)
    await waitFor(() => expect(sessionStorage.getItem('bda_token')).toBe('invited-access'))
    expect(body).toEqual({ username: 'alice', display_name: 'Alice', password: 'Example-pass-123', invitation_token: 'synthetic-invitation' })
  })

  it.each([LoginPage, RegisterPage])('routes Public account entry to Private and offers anonymous browsing', async Page => {
    const submit = vi.fn(() => HttpResponse.json({}))
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({ ...config, deployment_kind: 'public', registration_mode: 'closed' })), http.post('*/api/v2/auth/register', submit))
    renderWithProviders(<Page />)
    expect(await screen.findByRole('link', { name: 'Create a Private account' })).toHaveAttribute('href', 'http://localhost:5177/#/register')
    expect(screen.getByRole('link', { name: 'Sign in to Private' })).toHaveAttribute('href', 'http://localhost:5177/#/login')
    expect(screen.getByRole('link', { name: 'View Public without an account' })).toHaveAttribute('href', '#/public')
    expect(document.querySelector('form')).toBeNull()
    expect(submit).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('bda_token')).toBeNull()
  })

  it('shows closed registration and disables registration when config is unavailable', async () => {
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({ ...config, registration_mode: 'closed' })))
    const view = renderWithProviders(<RegisterPage />)
    await screen.findByText('Registration is closed. Contact your workspace administrator.')
    expect(document.querySelector('form')).toBeNull()
    view.unmount()
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({}, { status: 503 })))
    renderWithProviders(<RegisterPage />)
    await screen.findByText(/Workspace settings could not be loaded/)
    expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled()
  })

  it('keeps existing password login available when config fails and preserves a safe deep link', async () => {
    window.location.hash = '#/login?returnTo=%2Faccount'
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({}, { status: 503 })), http.post('*/api/v2/auth/token', () => HttpResponse.json({ access_token: 'access', user })))
    renderWithProviders(<LoginPage />)
    await screen.findByText(/Workspace settings could not be loaded/)
    field('Username', 'alice'); field('Password', 'Example-pass-123')
    fireEvent.submit(document.querySelector('form')!)
    await waitFor(() => expect(window.location.hash).toBe('#/account'))
  })

  it('recovers via a manually entered code without promising an email', async () => {
    let body: unknown
    server.use(http.post('*/api/v2/auth/password/reset', async ({ request }) => { body = await request.json(); return new HttpResponse(null, { status: 204 }) }))
    renderWithProviders(<ResetPasswordPage />)
    expect(screen.getByText(/does not send recovery emails/)).toBeVisible()
    field('Recovery code', 'synthetic-one-use-code'); field('New password', 'Updated-pass-123'); field('Confirm password', 'Updated-pass-123')
    fireEvent.submit(document.querySelector('form')!)
    await waitFor(() => expect(window.location.hash).toBe('#/login?notice=password-updated'))
    expect(body).toEqual({ token: 'synthetic-one-use-code', new_password: 'Updated-pass-123' })
  })

  it('shows no administrator controls to ordinary members and changes password with If-Match', async () => {
    let match: string | null = null
    server.use(http.get('*/api/v2/auth/account', () => HttpResponse.json(user)), http.post('*/api/v2/auth/password', ({ request }) => { match = request.headers.get('If-Match'); return new HttpResponse(null, { status: 204 }) }))
    renderWithProviders(<AccountPage />)
    await screen.findByText('Alice')
    expect(screen.queryByText('Invitations & account recovery')).not.toBeInTheDocument()
    field('Current password', 'Original-pass-123'); field('New password', 'Updated-pass-123'); field('Confirm password', 'Updated-pass-123')
    fireEvent.submit(document.querySelector('form')!)
    await waitFor(() => expect(window.location.hash).toBe('#/login?notice=password-updated'))
    expect(match).toBe('W/"4"')
  })

  it('shows admin code history without secret tokens and revokes with the row version', async () => {
    const grant = { id: 'grant-test', version: 3, username: 'invited-person', purpose: 'invitation', expires_at: '2099-01-01T00:00:00Z', used_at: null, revoked_at: null }
    let revoked = false
    server.use(http.get('*/api/v2/auth/account', () => HttpResponse.json({ ...user, role: 'admin' })), http.get('*/api/v2/auth/grants', () => HttpResponse.json({ items: [{ ...grant, revoked_at: revoked ? '2026-10-12T00:00:00Z' : null }], next_cursor: null })), http.get('*/api/v2/organizations', () => HttpResponse.json([])), http.post('*/api/v2/auth/grants/grant-test/revoke', ({ request }) => { expect(request.headers.get('If-Match')).toBe('W/"3"'); revoked = true; return HttpResponse.json(grant) }))
    renderWithProviders(<AccountPage />)
    await screen.findByText('Invitations & account recovery')
    fireEvent.click(await screen.findByRole('button', { name: 'Revoke' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Revoke' })).not.toBeInTheDocument())
    expect(screen.queryByLabelText('Invitation code')).not.toBeInTheDocument()
  })
})

describe('portal navigation', () => {
  it.each(['https://evil.test', '//evil.test', '/\\evil.test', '/login', '/projects\nhttps://evil.test'])('rejects unsafe return path %s', value => expect(safeReturnTo(value)).toBe('/projects'))
  it('only constructs explicit trusted portal roots and never transfers query strings or credentials', () => {
    expect(portalLoginUrl('https://research.example.org')).toBe('https://research.example.org/#/login')
    expect(portalUrl('https://research.example.org', 'public')).toBe('https://research.example.org/#/public')
    expect(portalUrl('https://research.example.org', 'register')).toBe('https://research.example.org/#/register')
    for (const value of ['javascript:alert(1)', 'http://example.org', 'https://u:p@example.org', 'https://example.org/?token=secret']) expect(portalLoginUrl(value)).toBeNull()
  })
})

it('never loads the anonymous service identity as a personal account', async () => {
  sessionStorage.setItem('bda_user', JSON.stringify({ public_visitor: true, role: 'viewer' }))
  const loadAccount = vi.fn(() => HttpResponse.json(user))
  server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({ ...config, deployment_kind: 'public' })), http.get('*/api/v2/auth/account', loadAccount))
  renderWithProviders(<AccountPage />)
  expect(await screen.findByRole('link', { name: 'Create a Private account' })).toHaveAttribute('href', 'http://localhost:5177/#/register')
  expect(loadAccount).not.toHaveBeenCalled()
  expect(screen.queryByText('Alice')).not.toBeInTheDocument()
})
