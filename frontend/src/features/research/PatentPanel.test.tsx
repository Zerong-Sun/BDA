import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { PatentPanel } from './PatentPanel'

const landscape = {
  records_matched: 2, records_listed: 2, documents_truncated: false,
  families: { distinct: 1, publications_without_family_id: 1, groups_truncated: false, groups: [{
    family_id: '100', publications: 1, jurisdictions: ['EP'], applicants: ['Example'], members_truncated: false,
    members: [{ document_id: 'doc1', title: 'Saved patent', publication_number: 'EP100' }],
  }] },
  records: [{ document_id: 'doc2', title: 'Unassigned patent', publication_number: 'WO200', family_id: null }],
}
function stub(write: boolean) {
  server.use(
    http.get('/api/v2/projects/:id/access', () => HttpResponse.json({ project_id: 'p1', role: write ? 'owner' : 'viewer', permissions: { read: true, write } })),
    http.get('/api/v2/projects/:id/patents/landscape', () => HttpResponse.json(landscape)),
  )
}
afterEach(cleanup)
it('shows saved families and keeps publications with no family visible to readers', async () => {
  stub(false)
  renderWithProviders(<PatentPanel projectId="p1" />)
  expect(await screen.findByText('Family 100 · 1')).toBeInTheDocument()
  expect(screen.getByText('WO200 — Unassigned patent')).toBeInTheDocument()
  screen.getAllByRole('button', { name: 'Retrieve claims' }).forEach((button) => expect(button).toBeDisabled())
})
it('queues retrieval and reports worker progress rather than treating acceptance as success', async () => {
  stub(true)
  let body: unknown
  server.use(
    http.post('/api/v2/projects/:id/patents/claims-lookups', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({ operation_id: 'op1', lookup_id: 'lookup1', status: 'queued', documents: 1, database: 'epo_ops_claims' }, { status: 202 })
    }),
    http.get('/api/v2/operations/op1', () => HttpResponse.json({ id: 'op1', status: 'running' })),
  )
  renderWithProviders(<PatentPanel projectId="p1" />)
  const buttons = await screen.findAllByRole('button', { name: 'Retrieve claims' })
  await waitFor(() => expect(buttons[0]).toBeEnabled())
  fireEvent.click(buttons[0])
  expect(await screen.findByText('Queued; waiting for retrieval results…')).toBeInTheDocument()
  expect(body).toEqual({ document_ids: ['doc1'] })
})
it('searches saved claims with project scope and fetches subsequent cursor pages', async () => {
  stub(false)
  const requests: URL[] = []
  server.use(http.get('/api/v2/projects/p1/patents/claims', ({ request }) => {
    const url = new URL(request.url); requests.push(url)
    const second = url.searchParams.has('cursor')
    return HttpResponse.json({ items: [{ claim_id: second ? 'c2' : 'c1', document_id: 'doc1', title: 'Saved patent', excerpt: second ? 'Second source passage' : 'First source passage', claim_number: second ? '2' : '1', language: 'en', retrieval_trace_id: 'trace1' }], next_cursor: second ? null : 'next' })
  }))
  renderWithProviders(<PatentPanel projectId="p1" />)
  fireEvent.change(screen.getByRole('textbox', { name: 'Search saved claims' }), { target: { value: '  sensor  ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Search text' }))
  expect(await screen.findByText('First source passage')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'More results' }))
  expect(await screen.findByText('Second source passage')).toBeInTheDocument()
  expect(requests[0].searchParams.get('query')).toBe('sensor')
  expect(requests[1].searchParams.get('cursor')).toBe('next')
})
