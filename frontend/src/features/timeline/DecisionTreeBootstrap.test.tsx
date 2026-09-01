import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DecisionTreeBootstrap } from './DecisionTreeBootstrap'

const { createDecisionTreeDraft, waitForDecisionTreeDraft, importDecisionTree } = vi.hoisted(() => ({
  createDecisionTreeDraft: vi.fn(),
  waitForDecisionTreeDraft: vi.fn(),
  importDecisionTree: vi.fn(),
}))

vi.mock('../../lib/api/decisionTree', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/decisionTree')>(
    '../../lib/api/decisionTree',
  )
  return { ...actual, createDecisionTreeDraft, waitForDecisionTreeDraft, importDecisionTree }
})

const DRAFT = {
  id: 'd1',
  project_id: 'p1',
  status: 'ready',
  error: null,
  draft: {
    goals: [
      { title: 'expressible candidate', detail: '', children: [{ title: 'disulfides', detail: '', children: [] }] },
    ],
    branches: [
      { title: 'activates the receptor?', summary: '', lane: 'wet' as const, goal_title: 'disulfides', alternatives: [] },
    ],
  },
}

beforeEach(() => {
  createDecisionTreeDraft.mockReset().mockResolvedValue({ draft_id: 'd1' })
  waitForDecisionTreeDraft.mockReset().mockResolvedValue(DRAFT)
  importDecisionTree.mockReset().mockResolvedValue({ goals_created: 2, branches_created: 1 })
})

afterEach(cleanup)

async function draft() {
  renderWithProviders(<DecisionTreeBootstrap projectId="p1" hasPrompt />)
  fireEvent.click(screen.getByRole('button', { name: /draft from the prompt/i }))
  await waitFor(() => expect(screen.getByDisplayValue('expressible candidate')).toBeInTheDocument())
}

describe('DecisionTreeBootstrap', () => {
  it('refuses to draft without a prompt to draft from', () => {
    renderWithProviders(<DecisionTreeBootstrap projectId="p1" hasPrompt={false} />)
    expect(screen.getByText(/no design prompt yet/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /draft from the prompt/i })).not.toBeInTheDocument()
  })

  it('writes nothing until the reviewer submits', async () => {
    await draft()
    // The draft is on screen and editable; nothing has been written.
    expect(importDecisionTree).not.toHaveBeenCalled()
  })

  it('submits only what survived the review', async () => {
    await draft()
    fireEvent.change(screen.getByLabelText(/goal: disulfides/i), { target: { value: 'cysteine pairing' } })
    fireEvent.click(screen.getByRole('button', { name: /write 2 goals and 1 questions/i }))

    await waitFor(() => expect(importDecisionTree).toHaveBeenCalledTimes(1))
    const [, proposal] = importDecisionTree.mock.calls[0]
    // Renaming a goal carried its branch, so the submitted proposal is still consistent.
    expect(proposal.goals[0].children[0].title).toBe('cysteine pairing')
    expect(proposal.branches[0].goal_title).toBe('cysteine pairing')
  })

  it('dropping a goal drops the questions filed under it', async () => {
    await draft()
    const goalRow = screen.getByLabelText(/goal: disulfides/i).closest('li') as HTMLElement
    fireEvent.click(within(goalRow).getByRole('button', { name: /drop/i }))

    fireEvent.click(screen.getByRole('button', { name: /write 1 goals and 0 questions/i }))
    await waitFor(() => expect(importDecisionTree).toHaveBeenCalledTimes(1))
    const [, proposal] = importDecisionTree.mock.calls[0]
    expect(proposal.branches).toEqual([])
  })

  it('lets the reviewer change which half answers a question', async () => {
    await draft()
    fireEvent.click(
      screen.getByRole('combobox', { name: /where activates the receptor\? gets answered/i }),
    )
    const both = await screen.findByRole('option', { name: /dry and wet/i })
    fireEvent.pointerDown(both, { button: 0 })
    fireEvent.pointerUp(both, { button: 0 })
    fireEvent.click(both)

    fireEvent.click(screen.getByRole('button', { name: /write 2 goals and 1 questions/i }))
    await waitFor(() => expect(importDecisionTree).toHaveBeenCalledTimes(1))
    expect(importDecisionTree.mock.calls[0][1].branches[0].lane).toBe('both')
  })

  it('surfaces a failed draft instead of showing an empty review', async () => {
    waitForDecisionTreeDraft.mockResolvedValue({ ...DRAFT, status: 'failed', error: 'no_llm_provider_configured' })
    renderWithProviders(<DecisionTreeBootstrap projectId="p1" hasPrompt />)
    fireEvent.click(screen.getByRole('button', { name: /draft from the prompt/i }))
    await waitFor(() => expect(screen.getByText(/no_llm_provider_configured/)).toBeInTheDocument())
  })
})
