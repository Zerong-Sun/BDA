import { cleanup, fireEvent, screen, within } from '@testing-library/react'
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
function respond(content: string | null = report, references: Record<string, unknown>[] = [], updatedAt: string | undefined = '2026-09-16T00:00:00Z') {
  server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({
    project: { id: project.id },
    review_document: content === null ? null : { id: 'review', title: { en: 'Saved report' }, content: { en: content }, status: 'accepted', version: 1, updated_at: updatedAt },
    review_sections: [{ items: [{ id: 'finding', evidence: { review_status: 'pending_review' } }] }], references, structures: [],
  })))
}
beforeEach(() => { useAppStore.setState({ language: 'en' }); respond() })
afterEach(cleanup)
describe('archived research overview', () => {
  it('surfaces archive maintenance instructions without presenting its index as a results report', async () => {
    server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({
      project: { id: project.id },
      review_document: { id: 'index', title: { zh: '项目条目索引', en: 'Project entry index' }, content: { en: '# Archived source index\n## Next steps\nRemain archived; retain traceability only.' }, status: 'progress_note', version: 1, updated_at: '2026-10-16T00:00:00Z' },
      review_sections: [], references: [], structures: [],
    })))
    renderWithProviders(<ProjectResearchOverview project={project} />)
    const next = await screen.findByRole('region', { name: 'Open questions and advancement conditions' })
    expect(within(next).getByText('Remain archived; retain traceability only.')).toBeVisible()
    expect(within(next).getByText(/Source: maintenance instructions in the archive index/)).toBeVisible()
    expect(within(screen.getByRole('region', { name: 'Project results' })).getByText(/Only an archive index is recorded/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Read full report' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive source index' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('shows current readiness and its next step even without a next-steps heading', async () => {
    respond('## Results\nRecorded checks.\n## 当前准备判定\n当前资源未齐备。最有价值的下一步是补齐输入。')
    renderWithProviders(<ProjectResearchOverview project={project} />)
    const next = await screen.findByRole('region', { name: 'Open questions and advancement conditions' })
    expect(within(next).getByText('当前资源未齐备。最有价值的下一步是补齐输入。')).toBeVisible()
    expect(within(next).queryByText(/no separate open-questions/)).not.toBeInTheDocument()
  })
  it('keeps an index-only archive accessible without presenting it as a results report', async () => {
    server.use(http.get('/api/v2/projects/:id/research-workspace', () => HttpResponse.json({
      project: { id: project.id },
      review_document: { id: 'index', title: { zh: '项目条目索引', en: 'Project entry index' }, content: { en: 'Retained migration source index.' }, status: 'progress_note', version: 1, updated_at: '2026-10-16T00:00:00Z' },
      review_sections: [], references: [], structures: [],
    })))
    renderWithProviders(<ProjectResearchOverview project={project} />)
    expect(await screen.findByText(/Only an archive index is recorded/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Read full report' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Recorded report status/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive source index' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Retained migration source index.')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Archive source index' }))
    expect(await screen.findByText('Retained migration source index.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'View Bot review records →' })).toHaveAttribute('href', '#/bots/auditor?project=archived&view=records')
  })
  it('reads existing objectives, findings and open questions even without structured goals', async () => {
    renderWithProviders(<ProjectResearchOverview project={project} />)
    expect(await screen.findByText('Which interactions are supported?')).toBeVisible()
    expect(screen.getByText('A saved structural finding.')).toBeVisible()
    const review = screen.getByRole('complementary', { name: 'Report and review' })
    expect(within(review).getByText('Pending review')).toBeVisible()
    expect(within(review).getByText(/Recorded report status/)).toHaveTextContent(/accepted/i)
    expect(within(review).getByText('Final review: not separately recorded in this research record')).toBeVisible()
    expect(screen.getByRole('link', { name: 'View Bot review records →' })).toHaveAttribute('href', '#/bots/auditor?project=archived&view=records')
    expect(screen.getAllByRole('heading', { level: 2 }).slice(0, 4).map(el => el.textContent)).toEqual(['Project results', 'Report and review', 'Next step and advancement conditions', 'Research objectives and questions'])
    expect(screen.getByRole('link', { name: 'Workflow and gates →' })).toHaveAttribute('href', '#/workflow?project=archived')
    expect(screen.getByRole('link', { name: 'Tasks and deliverables →' })).toHaveAttribute('href', '#/bots?project=archived&view=tasks')
    expect(screen.getByText('Cellular context remains unresolved.')).toBeVisible()
    expect(screen.queryByText(/No research questions yet/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '1 research findings →' })).toHaveAttribute('href', '#/research?project=archived&tab=evidence')
    fireEvent.click(screen.getByRole('button', { name: 'Full report and cited sources' }))
    expect(await screen.findByText('A retained source.')).toBeVisible()
  })
  it('shows unsectioned saved status and hold instructions without requiring a generated summary', async () => {
    respond('本轮状态：用户暂停。\n\n原始数据仍缺失，未制造数值。\n\n# Historical plan\n\n下一阶段取得材料。')
    renderWithProviders(<ProjectResearchOverview project={project} />)
    const results = await screen.findByRole('region', { name: 'Project results' })
    expect(within(results).getByText('本轮状态：用户暂停。')).toBeVisible()
    expect(within(results).getByText('原始数据仍缺失，未制造数值。')).toBeVisible()
    const next = screen.getByRole('region', { name: 'Open questions and advancement conditions' })
    expect(within(next).getByText('本轮状态：用户暂停。')).toBeVisible()
    expect(screen.queryByText('下一阶段取得材料。')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Full report and cited sources' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('keeps missing report distinct from a resolved project', async () => {
    respond(null)
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'completed' }} />)
    expect(await screen.findByText('Original scope')).toBeVisible()
    expect(screen.getByText(/No report is recorded/)).toBeVisible()
    expect(screen.getByText(/does not imply all questions are resolved/)).toBeVisible()
    expect(screen.getByText('Completed project · saved research record')).toBeVisible()
  })
  it('shows authored questions and opens the complete saved report from its primary action', async () => {
    respond(report.replace('Which interactions are supported?', 'Trace the recorded interactions.\n\n1. Which interface?\n2. Which cell context?'))
    renderWithProviders(<ProjectResearchOverview project={project} />)
    expect(await screen.findByText('Which interface?')).toBeVisible()
    expect(screen.getByText('Which cell context?')).toBeVisible()
    expect(screen.queryByText('A retained source.')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Read full report' }))
    expect(await screen.findByText('A retained source.')).toBeVisible()
  })
  it('opens a noncontiguous original citation number from the results summary', async () => {
    respond('## Research objective\nScope\n## Results\nA sourced result.[36]', [{ document_id: 'doc-36', ref_id: 'R036', title: { en: 'Saved source 36' }, url: 'https://example.org/source-36' }])
    renderWithProviders(<ProjectResearchOverview project={project} />)
    fireEvent.click(await screen.findByRole('link', { name: 'View source 1' }))
    expect(screen.getByRole('button', { name: '[1] Saved source 36' })).toHaveAttribute('aria-expanded', 'true')
  })
  it('keeps fallback brief prose separate from report citation numbering', async () => {
    respond('## Research questions\nWhich ligand?', [{ document_id: 'doc-1', ref_id: 'R001', title: { en: 'Report source' } }])
    renderWithProviders(<ProjectResearchOverview project={{ ...project, summary: 'Brief objective.[1]' }} />)
    expect(await screen.findByText('Which ligand?')).toBeVisible()
    expect(screen.getByText('Source: project brief')).toBeVisible()
    expect(screen.getByText('Brief objective.[1]')).toBeVisible()
    expect(screen.queryByRole('link', { name: /View source/ })).not.toBeInTheDocument()
  })
  it('keeps an active project in progress and shows the latest progress separately from its accepted report', async () => {
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [{ id: 'progress', title: 'Latest saved progress note', status: 'progress_note', updated_at: '2026-10-16T06:39:00Z', content: '## Results\nSaved computational output only.[1]\n## Next steps\nFunction remains untested.\n## Source details\nRetained progress source.' }], next_cursor: null })))
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    expect(await screen.findByText('Saved computational output only.[1]')).toBeVisible()
    expect(screen.getByText('In progress · saved research record')).toBeVisible()
    expect(screen.queryByText('A saved structural finding.')).not.toBeInTheDocument()
    expect(screen.getByText('Function remains untested.')).toBeVisible()
    expect(screen.queryByRole('link', { name: /View source/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Read latest progress' }))
    expect(await screen.findByText('Retained progress source.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Read full report' }))
    expect(await screen.findByText('A retained source.')).toBeVisible()
    expect(screen.getByText('Final review: not separately recorded in this research record')).toBeVisible()
  })
  it('shows an unsectioned progress record with its caveats when no result section exists', async () => {
    respond('## Research objective\nOriginal scope.')
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [{ id: 'progress', title: 'Recorded comparison', status: 'progress_note', updated_at: '2026-10-16T06:39:00Z', content: '# Recorded comparison\n\nReused two saved outputs.\n\nThis is a model score, not a measured affinity.' }], next_cursor: null })))
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    expect(await screen.findByText('Reused two saved outputs.')).toBeVisible()
    expect(screen.getByText('This is a model score, not a measured affinity.')).toBeVisible()
    expect(screen.getByText('Latest progress record (without section headings)')).toBeVisible()
    expect(screen.queryByText(/No separate results section/)).not.toBeInTheDocument()
  })
  it.each(['2026-09-01T00:00:00Z', 'invalid-date'])('does not overwrite a report with older or undated progress (%s)', async updatedAt => {
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [{ id: 'progress', title: 'Separate progress record', status: 'progress_note', updated_at: updatedAt, content: '## Results\nSeparate progress result.\n## Next steps\nSeparate progress condition.' }], next_cursor: null })))
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    expect(await screen.findByRole('button', { name: 'Read latest progress' })).toBeVisible()
    expect(screen.getByText('A saved structural finding.')).toBeVisible()
    expect(screen.getByText('Cellular context remains unresolved.')).toBeVisible()
    expect(screen.queryByText('Separate progress result.')).not.toBeInTheDocument()
    expect(screen.queryByText('Separate progress condition.')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Read latest progress' }))
    expect(await screen.findByText('Separate progress result.')).toBeVisible()
  })
  it('does not retain cached active progress after the project is archived', async () => {
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [{ id: 'progress', title: 'Cached progress', status: 'progress_note', updated_at: '2026-10-16T00:00:00Z', content: '## Results\nCached progress result.' }], next_cursor: null })))
    const { rerender } = renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    expect(await screen.findByText('Cached progress result.')).toBeVisible()
    rerender(<ProjectResearchOverview project={project} />)
    expect(screen.queryByText('Cached progress result.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Read latest progress' })).not.toBeInTheDocument()
    expect(screen.getByText('A saved structural finding.')).toBeVisible()
  })
  it('keeps the accepted report accessible when progress loading fails', async () => {
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ detail: 'Unavailable' }, { status: 503 })))
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    expect(await screen.findByText('A saved structural finding.')).toBeVisible()
    expect(await screen.findByRole('alert')).toHaveTextContent('latest progress is not confirmed')
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

describe('latest saved progress precedence', () => {
  it('does not fill newer progress without next steps with an old report instruction', async () => {
    respond('## Results\nOld result.\n## Next steps\nProceed with old plan.')
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [{ id: 'progress', title: 'Latest progress', status: 'progress_note', updated_at: '2026-10-19T00:00:00Z', content: '## Results\nCurrent result needs validation.' }], next_cursor: null })))
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    expect(await screen.findByText('Current result needs validation.')).toBeVisible()
    expect(screen.queryByText('Proceed with old plan.')).not.toBeInTheDocument()
    expect(screen.getByText(/previous report instructions are not current next steps/)).toBeVisible()
  })
  it.each(['# 项目已暂停\n\n用户要求暂停；以下仅为历史材料。', '用户要求暂停；以下仅为历史材料。'])('keeps current hold ahead of structured historical plans: %s', async hold => {
    respond(`${hold}\n\n# 历史计划\n\n## Next steps\n下一阶段：启动计算。`)
    renderWithProviders(<ProjectResearchOverview project={project} />)
    const next = await screen.findByRole('region', { name: 'Open questions and advancement conditions' })
    expect(within(next).getByText(/暂停/)).toBeVisible()
    expect(within(next).queryByText('下一阶段：启动计算。')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Full report and cited sources' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('shows preamble results and next steps while references remain collapsed', async () => {
    respond('当前结果：输入仍缺失。\n\n下一阶段：仅补齐记录。\n\n## References\nSaved source only.')
    renderWithProviders(<ProjectResearchOverview project={project} />)
    const results = await screen.findByRole('region', { name: 'Project results' })
    expect(within(results).getByText('当前结果：输入仍缺失。')).toBeVisible()
    expect(within(screen.getByRole('region', { name: 'Open questions and advancement conditions' })).getByText('下一阶段：仅补齐记录。')).toBeVisible()
    expect(screen.queryByText('Saved source only.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Full report and cited sources' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('does not hide newer failure prose behind an older positive report', async () => {
    respond('## Results\nPrevious result passed.\n## Next steps\nProceed to the next stage.')
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [{ id: 'new-failure', title: 'Latest failure record', status: 'progress_note', updated_at: '2026-10-19T00:00:00Z', content: '# Latest progress\n\nThe latest validation failed. Stop the next stage.' }], next_cursor: null })))
    renderWithProviders(<ProjectResearchOverview project={{ ...project, status: 'active' }} />)
    await screen.findByRole('button', { name: 'Read latest progress' })
    expect(within(screen.getByRole('region', { name: 'Project results' })).getByText('The latest validation failed. Stop the next stage.')).toBeVisible()
    expect(within(screen.getByRole('region', { name: 'Open questions and advancement conditions' })).queryByText('Proceed to the next stage.')).not.toBeInTheDocument()
  })
})
