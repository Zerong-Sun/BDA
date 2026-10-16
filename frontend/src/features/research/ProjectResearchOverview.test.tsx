import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import type { Project } from '../../lib/api/projects'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/mocks/handlers'
import { ProjectResearchOverview } from './ProjectResearchOverview'
import { reviewSections } from './reviewSections'

const project: Project = { id: 'archived', organization_id: 'org', owner_id: 'owner', name: 'Saved study', project_type: 'research', status: 'archived', summary: 'Original scope', primary_target_id: null, version: 1, created_at: '', updated_at: '' }
const report = '## Research objective\nWhich interactions are supported?\n\n## Structure and signaling\nA saved structural finding.\n\n## Uncertainty\nCellular context remains unresolved.\n\n## References\nA retained source.'
function respond(content: string | null = report) {
  server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({
    project: { id: project.id },
    review_document: content === null ? null : { id: 'review', title: { en: 'Saved report' }, content: { en: content }, status: 'accepted', version: 1 },
    review_sections: [{ items: [{ id: 'finding' }] }], references: [], structures: [],
  })))
}
beforeEach(() => { useAppStore.setState({ language: 'en' }); respond() })
afterEach(cleanup)
describe('archived research overview', () => {
  it('reads existing objectives, findings and open questions even without structured goals', async () => {
    renderWithProviders(<ProjectResearchOverview project={project} />)
    expect(await screen.findByText('Which interactions are supported?')).toBeVisible()
    expect(screen.getByText('A saved structural finding.')).toBeVisible()
    expect(screen.getByText('Cellular context remains unresolved.')).toBeVisible()
    expect(screen.queryByText(/No research questions yet/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '1 research findings →' })).toHaveAttribute('href', '#/research?project=archived&tab=evidence')
    fireEvent.click(screen.getByRole('button', { name: 'Full report and cited sources' }))
    expect(await screen.findByText('A retained source.')).toBeVisible()
  })
  it('keeps missing report distinct from a resolved project', async () => {
    respond(null)
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'completed' }} />)
    expect(await screen.findByText('Original scope')).toBeVisible()
    expect(screen.getByText(/No report is recorded/)).toBeVisible()
    expect(screen.getByText(/does not imply all questions are resolved/)).toBeVisible()
    expect(screen.getByText('Completed project · saved research record')).toBeVisible()
  })
  it('reports fetch failures with a retry rather than empty goals', async () => {
    server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({ detail: 'unavailable' }, { status: 503 })))
    renderWithProviders(<ProjectResearchOverview project={project} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load')
    respond()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Which interactions are supported?')).toBeVisible()
  })
})
it('does not interpret fenced report code or reference headings as overview sections', () => {
  expect(reviewSections('## Research objective\nKeep this.\n```md\n## Not a heading\n```\n## References\nSource.')).toEqual([{ title: 'Research objective', body: 'Keep this.\n```md\n## Not a heading\n```' }])
})
