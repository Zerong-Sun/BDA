import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import type { EvidenceNote } from './evidenceNotes'
import { decisionReadiness } from './decisionReadiness'
import { ResearchDecisionCenter } from './ResearchDecisionCenter'
import { ResearchDecisionEditor } from './ResearchDecisionEditor'

const api = vi.hoisted(() => ({ goals: vi.fn(), evidence: vi.fn(), timeline: vi.fn(), save: vi.fn(), writable: true }))
vi.mock('../../lib/api/researchGoals', () => ({ listResearchGoals: api.goals }))
vi.mock('../../lib/api/evidenceNotes', () => ({ listEvidenceNotes: api.evidence }))
vi.mock('../../lib/api/timeline', () => ({ listAllTimeline: api.timeline }))
vi.mock('../../lib/api/researchDecision', () => ({ updateResearchDecision: api.save }))
vi.mock('../../lib/hooks/useProjectAccess', () => ({ useProjectAccess: () => ({ data: { permissions: { write: api.writable } } }) }))

const contract = {
  hypothesis: 'A repeatable effect exists under defined conditions', alternatives: ['Replicate the assay', 'Change the measurement method'],
  success_criteria: ['At least three independent repeats exceed the threshold'],
  falsification_criteria: ['The same signal appears in negative controls'],
  next_decision: 'Continue only after independent replication', evidence_note_ids: ['note-one'],
}
const goal: ResearchGoal = { id: 'goal-one', project_id: 'project-one', parent_id: null, title: 'Does the effect reproduce?', detail: '', status: 'open', sort_order: 0, tags: [], links: [], version: 7, created_at: '', updated_at: '', decision_contract: contract }
const note: EvidenceNote = { id: 'note-one', document_id: 'document-one', document_title: 'A controlled assay', argument: 'The apparent effect may be an artefact', argument_id: 'argument-one', paper_claim: 'The control also showed a signal', interpretation: 'Control for the assay signal', limitations: 'Only one assay condition', relation: 'contradicts', quote: 'The control had a similar signal.', locator: 'Results', source_url: 'https://example.org/paper', source_ref: {}, anchor_status: 'matched', review_status: 'accepted', reviewed_by: 'reviewer', reviewed_at: '', version: 1, created_at: '', updated_at: '' }

beforeEach(() => {
  vi.clearAllMocks()
  api.writable = true
  window.location.hash = '#/research?project=project-one&tab=goals'
  useAppStore.setState({ language: 'en', appMode: 'application' })
  api.goals.mockResolvedValue([goal])
  api.evidence.mockResolvedValue({ items: [note], next_cursor: null })
  api.timeline.mockResolvedValue([{ id: 'decision-one', occurred_at: '2026-10-10T00:00:00Z', entry_type: 'result', decided_by: 'human', title: 'Control invalidated the earlier interpretation', summary: 'Retest after fixing the control.', outcome: 'refuted', supersedes_id: 'earlier-id', alternatives: [] }])
  api.save.mockResolvedValue({ ...goal, version: 8 })
})
afterEach(cleanup)

describe('decision definition checks', () => {
  it('leaves missing criteria unknown and never interprets a goal status as experimental success', () => {
    const state = decisionReadiness({ ...goal, status: 'answered', decision_contract: {} }, [], true)
    expect(state.readyForReview).toBe(false)
    expect(state.criteria.every((check) => !check.satisfied)).toBe(true)
  })

  it('does not silently remove counterevidence or treat documentation readiness as a truth verdict', () => {
    const state = decisionReadiness(goal, [note], true)
    expect(state.readyForReview).toBe(true)
    expect(state.linked[0].relation).toBe('contradicts')
    expect(decisionReadiness(goal, [{ ...note, anchor_status: 'changed' }], true).readyForReview).toBe(false)
    expect(decisionReadiness(goal, [], false).missing).toEqual(['note-one'])
  })
})

describe('research decision center', () => {
  it('shows the selected question title before opening the selector and after switching questions', async () => {
    const secondGoal = { ...goal, id: 'goal-two', title: 'Does the designed binder hold at bench concentrations?' }
    api.goals.mockResolvedValue([goal, secondGoal])
    window.location.hash = '#/research?project=project-one&tab=goals&goal=goal-two'
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    const selector = await screen.findByRole('combobox', { name: 'Current question' })
    expect(selector).toHaveAttribute('aria-expanded', 'false')
    expect(selector).toHaveTextContent(secondGoal.title)
    expect(selector).not.toHaveTextContent(secondGoal.id)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    fireEvent.click(selector)
    const option = await screen.findByRole('option', { name: goal.title })
    fireEvent.pointerDown(option, { button: 0 })
    fireEvent.pointerUp(option, { button: 0 })
    fireEvent.click(option)
    await waitFor(() => expect(selector).toHaveAttribute('aria-expanded', 'false'))
    expect(selector).toHaveTextContent(goal.title)
    expect(selector).not.toHaveTextContent(goal.id)
  })

  it('shows hypothesis, alternatives, criteria and original counterevidence alongside real learning records', async () => {
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    expect(await screen.findByText(contract.hypothesis)).toBeVisible()
    expect(await screen.findByText(note.quote)).toBeVisible()
    expect(screen.getByText(contract.falsification_criteria[0])).toBeVisible()
    expect(screen.getByText(note.limitations, { exact: false })).toBeVisible()
    expect(screen.getByRole('link', { name: note.document_title })).toHaveAttribute('href', note.source_url)
    const ledger = screen.getByRole('region', { name: 'Project learning ledger' })
    expect(within(ledger).getByText('Control invalidated the earlier interpretation')).toBeVisible()
    expect(api.save).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Learning & next experiments' })).toHaveAttribute('href', '#/learning?project=project-one')
  })

  it('preserves explicit criteria and the displayed version when saving human edits', async () => {
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit decision definition' }))
    const form = screen.getByRole('form', { name: 'Edit decision definition' })
    fireEvent.change(within(form).getByRole('textbox', { name: 'Testable hypothesis' }), { target: { value: 'A revised testable hypothesis' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save decision definition' }))
    await waitFor(() => expect(api.save).toHaveBeenCalledWith('goal-one', 7, { ...contract, hypothesis: 'A revised testable hypothesis' }))
  })

  it('keeps an unsaved definition when the server rejects a stale edit', async () => {
    api.save.mockRejectedValue(new Error('Goal was modified; reload before retrying'))
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit decision definition' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save decision definition' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('reload before retrying')
    expect(screen.getByRole('textbox', { name: 'Testable hypothesis' })).toHaveValue(contract.hypothesis)
  })

  it('does not adopt a refreshed server version while a draft remains open', async () => {
    const close = vi.fn()
    const view = renderWithProviders(<ResearchDecisionEditor projectId="project-one" goal={goal} notes={[note]} complete onClose={close} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Testable hypothesis' }), { target: { value: 'My unsaved hypothesis' } })
    view.rerender(<ResearchDecisionEditor projectId="project-one" goal={{ ...goal, version: 9, decision_contract: { ...contract, hypothesis: 'Someone else changed the definition' } }} notes={[note]} complete onClose={close} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save decision definition' }))
    await waitFor(() => expect(api.save).toHaveBeenCalledWith('goal-one', 7, expect.objectContaining({ hypothesis: 'My unsaved hypothesis' })))
  })

  it('makes failed data reads explicit rather than presenting empty data as a scientific finding', async () => {
    api.evidence.mockRejectedValue(new Error('Source unavailable'))
    api.timeline.mockRejectedValue(new Error('Timeline unavailable'))
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    expect(await screen.findByText(/Evidence could not be loaded; this does not mean it is absent/)).toBeVisible()
    expect(await screen.findByText(/History could not be loaded/)).toBeVisible()
    expect(screen.queryByText(/Documentation ready/)).not.toBeInTheDocument()
  })

  it('keeps the decision center read-only for viewers and demo mode', async () => {
    api.writable = false
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    await screen.findByText(contract.hypothesis)
    expect(screen.queryByRole('button', { name: 'Edit decision definition' })).not.toBeInTheDocument()
  })

  it('keeps recent history as a short index to the canonical decision record', async () => {
    api.timeline.mockResolvedValue(Array.from({ length: 4 }, (_, index) => ({ id: `entry-${index}`, occurred_at: `2026-10-0${index + 1}T00:00:00Z`, entry_type: 'decision', decided_by: 'human', title: `Recorded decision ${index}`, summary: 'Full reasoning belongs in the decision record.', outcome: 'open', alternatives: [] })))
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    const ledger = screen.getByRole('region', { name: 'Project learning ledger' })
    expect(await within(ledger).findByRole('link', { name: 'Recorded decision 3' })).toHaveAttribute('href', '#/research?project=project-one&tab=timeline')
    expect(within(ledger).queryByText('Recorded decision 0')).not.toBeInTheDocument()
    expect(within(ledger).getAllByRole('article')).toHaveLength(3)
    expect(within(ledger).queryByText('Full reasoning belongs in the decision record.')).not.toBeInTheDocument()
  })

  it('marks linked records as not yet loaded when evidence pagination remains', async () => {
    api.evidence.mockResolvedValue({ items: [], next_cursor: 'more' })
    renderWithProviders(<ResearchDecisionCenter projectId="project-one" />)
    expect(await screen.findByText(/linked evidence records are not yet loaded/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Load more evidence' })).toBeEnabled()
    expect(screen.queryByText(/linked evidence records are unavailable/)).not.toBeInTheDocument()
  })
})
