import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { createElement, type ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { useAppStore } from '../../lib/store/appStore'
import { requireCopilotWrite, useCopilotReadOnly } from './commandAccess'

vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ projectId: 'project-access' }) }))

afterEach(() => { sessionStorage.clear(); useAppStore.setState({ appMode: 'application' }) })

function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: new QueryClient({ defaultOptions: { queries: { retry: false } } }) }, children)
}

it.each(['viewer', 'demo'])('rejects a command even if a disabled control is bypassed in %s mode', (mode) => {
  useAppStore.setState({ appMode: mode === 'demo' ? 'demo' : 'application', language: 'en' })
  sessionStorage.setItem('bda_user', JSON.stringify({ role: mode === 'viewer' ? 'viewer' : 'researcher' }))
  expect(() => requireCopilotWrite()).toThrow('This workspace is read-only.')
})

it('treats a project viewer as read-only even when the global role may write', async () => {
  sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
  server.use(http.get('/api/v2/projects/:projectId/access', () => HttpResponse.json({ project_id: 'project-access', role: 'viewer', permissions: { read: true, write: false } })))
  const { result } = renderHook(() => useCopilotReadOnly(), { wrapper })
  await waitFor(() => expect(result.current).toBe(true))
})

it('lets a project researcher act', async () => {
  sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
  server.use(http.get('/api/v2/projects/:projectId/access', () => HttpResponse.json({ project_id: 'project-access', role: 'researcher', permissions: { read: true, write: true } })))
  const { result } = renderHook(() => useCopilotReadOnly(), { wrapper })
  await waitFor(() => expect(result.current).toBe(false))
})
