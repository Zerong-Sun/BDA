import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { renderWithProviders } from '../test/renderWithProviders'
import { server } from '../test/mocks/handlers'
import { PublicWorkspacePage } from './PublicWorkspace'
import { WorkspaceAccessGate } from '../features/account/WorkspaceAccessGate'
import { isPublicVisitor } from '../lib/auth/publicWorkspace'

const config = { deployment_kind:'public', registration_mode:'closed', realm:'public', public_workspace_enabled:true, public_portal_url:'http://localhost:5176', private_portal_url:'http://localhost:5177' }
const viewer = { id:'public-reader', username:'public-reader', display_name:'Public visitor', role:'viewer' }
afterEach(() => { sessionStorage.clear(); window.location.hash = '' })
function setup() {
  server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json(config)), http.get('*/api/v2/auth/me', () => HttpResponse.json(viewer)))
  renderWithProviders(<Routes><Route path="/public" element={<PublicWorkspacePage />} /><Route element={<WorkspaceAccessGate />}><Route path="/projects" element={<h1>Project workbench</h1>} /><Route path="/tools" element={<h1>Lab tools</h1>} /><Route path="/workflow" element={<h1>Workflow</h1>} /></Route><Route path="/login" element={<h1>Private login</h1>} /></Routes>)
}

describe('Public opens the complete workspace', () => {
  it('redirects the former showcase entry into the same project workbench without a token', async () => {
    window.location.hash = '#/public'; setup()
    expect(await screen.findByRole('heading', {name:'Project workbench'})).toBeVisible()
    expect(window.location.hash).toBe('#/projects')
    expect(sessionStorage.getItem('bda_token')).toBeNull()
    expect(isPublicVisitor()).toBe(true)
  })
  it('supports direct workspace deep links without a login screen', async () => {
    window.location.hash = '#/workflow?project=public-project'; setup()
    expect(await screen.findByRole('heading', {name:'Workflow'})).toBeVisible()
    expect(window.location.hash).toContain('project=public-project')
  })
  it('keeps the old Public tools link working in the full workspace', async () => {
    window.location.hash = '#/public?view=tools'; setup()
    expect(await screen.findByRole('heading', {name:'Lab tools'})).toBeVisible()
  })
  it('preserves the requested project and tool when resolving the Public entry', async () => {
    window.location.hash = '#/public?view=tools&project=public-project&tool=protein-properties'; setup()
    expect(await screen.findByRole('heading', {name:'Lab tools'})).toBeVisible()
    expect(window.location.hash).toBe('#/tools?project=public-project&tool=protein-properties')
  })
  it('keeps Private deep links protected and preserves their destination', async () => {
    window.location.hash = '#/workflow?project=private-project'; setup()
    server.use(http.get('*/api/v2/auth/config', () => HttpResponse.json({...config, deployment_kind:'private', public_workspace_enabled:false})), http.post('*/api/v2/auth/refresh', () => new HttpResponse(null, { status: 401 })))
    expect(await screen.findByRole('heading', {name:'Private login'})).toBeVisible()
    expect(window.location.hash).toBe('#/login?returnTo=%2Fworkflow%3Fproject%3Dprivate-project')
    expect(isPublicVisitor()).toBe(false)
  })
  it('shows a retry when the published viewer cannot be loaded instead of pretending to log in', async () => {
    window.location.hash = '#/projects'; setup()
    server.use(http.get('*/api/v2/auth/me', () => new HttpResponse(null,{status:503})))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
    await waitFor(() => expect(sessionStorage.getItem('bda_user')).toBeNull())
    expect(screen.queryByRole('heading',{name:'Private login'})).not.toBeInTheDocument()
  })
})
