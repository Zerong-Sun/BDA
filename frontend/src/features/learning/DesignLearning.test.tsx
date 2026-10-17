import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import * as memory from '../../lib/api/designMemory'
import { DesignLearningPanel, DesignLessonLibrary } from './DesignLearning'

vi.mock('../../lib/api/designMemory', () => ({ getDesignLearning: vi.fn(), listDesignLessons: vi.fn(), saveDesignReview: vi.fn(), saveDesignFeedback: vi.fn(), recordManualExecution: vi.fn(), createDesignLesson: vi.fn(), importDesignLesson: vi.fn() }))
vi.mock('../../lib/api/projects', () => ({ listProjects: vi.fn(async () => []) }))
const lesson: memory.Lesson = { id: 'lesson-1', created_at: '2026-10-17T00:00:00Z', created_by: 'user', project_id: 'p', review_id: null, item_key: null, supersedes_id: null, payload: { title: 'Conditional lesson', statement: 'Effect may depend on state', conditions: 'Only matched state A', limitations: 'No functional validation', evidence: ['record:one'], outcome: 'hypothesis', next_design_change: 'Add state B control' } }
const state: memory.DesignLearning = { manual_only: false, manual_execution: false, manual_execution_complete: false, required: true, state: 'missing', workflow_version: 4, fingerprint: 'a'.repeat(64), memory_digest: 'b'.repeat(64), checklist: [{ key: 'identity', title: '身份', title_en: 'Identity', prompt: '对象', prompt_en: 'Identify inputs' }], lessons: [lesson], review: null, history: [], feedback: [], pending_feedback: [] }
beforeEach(() => { vi.resetAllMocks(); useAppStore.setState({ language: 'en' }); vi.mocked(memory.getDesignLearning).mockResolvedValue(state); vi.mocked(memory.listDesignLessons).mockResolvedValue([lesson]) })
afterEach(cleanup)

describe('design learning', () => {
  it('shows applicability and uncertainty without pre-approving prior experience', async () => {
    renderWithProviders(<DesignLearningPanel workflowId="w" projectId="p" workflowVersion={4} draft writable />)
    expect(await screen.findByText(/Pre-design review needed/)).toBeInTheDocument()
    expect(screen.getByText(/Only matched state A/)).toBeInTheDocument()
    expect(screen.getByText(/No functional validation/)).toBeInTheDocument()
    expect(screen.getAllByRole('combobox').every(el => el.textContent?.includes('Select'))).toBe(true)
    expect(memory.saveDesignReview).not.toHaveBeenCalled()
  })
  it('records a blocked execution separately from refuting a hypothesis', async () => {
    const review: memory.Review = { id: 'r', created_at: lesson.created_at, workflow_run_id: 'w', payload: { fingerprint: state.fingerprint, memory_digest: state.memory_digest, objective: 'Original objective', context: 'Original context', items: [{ key: 'identity', disposition: 'test', rationale: 'Unknown', hypothesis: 'Original hypothesis', action: 'One change', comparison: 'Matched control', readout: 'Units', decision_rule: 'Predefined rule' }], lesson_snapshots: [] } }
    vi.mocked(memory.getDesignLearning).mockResolvedValue({ ...state, state: 'frozen', review, history: [review], pending_feedback: ['identity'] })
    renderWithProviders(<DesignLearningPanel workflowId="w" projectId="p" workflowVersion={4} draft={false} writable />)
    expect(await screen.findByText(/A successful run does not prove a hypothesis/)).toBeInTheDocument()
    const fields = ['Lesson title', 'Conclusion or hypothesis', 'Conditions (object, state, method, environment)', 'Limits and uncertainty', 'Specific change for the next design', 'Evidence references (one URL, citation or record ID per line)']
    for (const label of fields) fireEvent.change(screen.getByLabelText(label), { target: { value: label === 'Lesson title' ? 'Blocked by dependency' : 'Observed record reference and limited scope' } })
    fireEvent.click(screen.getByRole('combobox', { name: 'Question from the original review' }))
    const question = await screen.findByRole('option', { name: /Original hypothesis/ })
    fireEvent.pointerDown(question, { button: 0 }); fireEvent.pointerUp(question, { button: 0 }); fireEvent.click(question)
    fireEvent.click(screen.getByRole('combobox', { name: 'Evidence assessment' }))
    const outcome = await screen.findByRole('option', { name: 'Execution blocked (hypothesis untested)' })
    fireEvent.pointerDown(outcome, { button: 0 }); fireEvent.pointerUp(outcome, { button: 0 }); fireEvent.click(outcome)
    fireEvent.click(screen.getByRole('button', { name: 'Save outcome to the lesson library' }))
    await waitFor(() => expect(memory.saveDesignFeedback).toHaveBeenCalledWith('w', expect.objectContaining({ review_id: 'r', item_key: 'identity', outcome: 'execution_blocked' })))
  })
  it('does not offer writes to a read-only project or present load failure as an empty memory', async () => {
    vi.mocked(memory.listDesignLessons).mockRejectedValue(new Error('Evidence unavailable'))
    renderWithProviders(<DesignLessonLibrary projectId="p" writable={false} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Evidence unavailable')
    expect(screen.queryByText(/No lessons recorded yet/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Record / revise a lesson' })).not.toBeInTheDocument()
  })
})
