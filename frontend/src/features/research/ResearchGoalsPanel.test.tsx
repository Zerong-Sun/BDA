import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { buildGoalTree, flattenGoalTree, type ResearchGoal } from '../../lib/api/researchGoals'
import { ResearchGoalsPanel } from './ResearchGoalsPanel'
import { useAppStore } from '../../lib/store/appStore'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  detach: vi.fn(),
}))

vi.mock('../../lib/api/researchGoals', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/researchGoals')>(
    '../../lib/api/researchGoals',
  )
  return {
    ...actual,
    listResearchGoals: api.list,
    createResearchGoal: api.create,
    updateResearchGoal: api.update,
    deleteResearchGoal: api.remove,
    detachFromResearchGoal: api.detach,
  }
})

function goal(overrides: Partial<ResearchGoal> & { id: string; title: string }): ResearchGoal {
  return {
    project_id: 'project-one',
    parent_id: null,
    detail: '',
    status: 'open',
    sort_order: 0,
    tags: [],
    links: [],
    version: 1,
    created_at: '2026-08-27T00:00:00Z',
    updated_at: '2026-08-27T00:00:00Z',
    ...overrides,
  } as ResearchGoal
}

describe('buildGoalTree', () => {
  it('nests children under their parent and records depth', () => {
    const tree = buildGoalTree([
      goal({ id: 'root', title: 'Can this bind?' }),
      goal({ id: 'child', title: 'Does it fold?', parent_id: 'root' }),
      goal({ id: 'grandchild', title: 'At 37C?', parent_id: 'child' }),
    ])
    expect(tree).toHaveLength(1)
    expect(flattenGoalTree(tree).map((node) => [node.goal.id, node.depth])).toEqual([
      ['root', 0],
      ['child', 1],
      ['grandchild', 2],
    ])
  })

  it('shows a goal whose parent is missing rather than dropping it', () => {
    // A goal nobody can see is a goal nobody can correct, so an unresolved parent
    // surfaces the child at the root instead of silently swallowing the subtree.
    const tree = buildGoalTree([goal({ id: 'orphan', title: 'Stray', parent_id: 'gone' })])
    expect(tree.map((node) => node.goal.id)).toEqual(['orphan'])
  })
})

describe('ResearchGoalsPanel', () => {
  beforeEach(() => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
    api.list.mockResolvedValue([
      goal({ id: 'root', title: 'Can this bind CBD?' }),
      goal({
        id: 'child',
        title: 'Does the scaffold fold?',
        parent_id: 'root',
        status: 'answered',
        links: [
          { id: 'link-one', goal_id: 'child', resource_type: 'candidate', resource_id: 'cand-1234abcd', note: '' },
        ],
      }),
    ])
    api.create.mockResolvedValue(goal({ id: 'new', title: 'New question' }))
    api.update.mockResolvedValue(goal({ id: 'child', title: 'Does the scaffold fold?' }))
    api.remove.mockResolvedValue({ id: 'child', deleted: true, removed_goals: 1 })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders the tree and what is hung on each goal', async () => {
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    expect(await screen.findByText('Can this bind CBD?')).toBeInTheDocument()
    expect(screen.getByText('Does the scaffold fold?')).toBeInTheDocument()
    // The attached candidate is the point of the tree: dry work and wet work hang on
    // the same question.
    expect(screen.getByText('candidate')).toBeInTheDocument()
    expect(screen.getByText('cand-123')).toBeInTheDocument()
  })

  it('creates a sub-goal under the goal whose plus button was pressed', async () => {
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    await screen.findByText('Can this bind CBD?')

    fireEvent.click(screen.getByLabelText('Add a sub-goal under Can this bind CBD?'))
    fireEvent.change(screen.getByLabelText('A question this project has to answer'), {
      target: { value: 'Does it stay soluble?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add goal' }))

    await waitFor(() =>
      expect(api.create).toHaveBeenCalledWith('project-one', {
        title: 'Does it stay soluble?',
        parent_id: 'root',
      }),
    )
  })

  it('sends the goal version when answering, so a stale edit is refused not merged', async () => {
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    await screen.findByText('Can this bind CBD?')

    fireEvent.click(screen.getByRole('combobox', { name: 'Status of Can this bind CBD?' }))
    const answered = await screen.findByRole('option', { name: 'answered' })
    fireEvent.pointerDown(answered, { button: 0 })
    fireEvent.pointerUp(answered, { button: 0 })
    fireEvent.click(answered)

    await waitFor(() =>
      expect(api.update).toHaveBeenCalledWith('root', 1, { status: 'answered' }),
    )
  })

  it('prevents viewer edits and status changes', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    useAppStore.setState({ appMode: 'application' })
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    await screen.findByText('Can this bind CBD?')
    expect(screen.getByLabelText('A question this project has to answer')).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Status of Can this bind CBD?' })).toBeDisabled()
    expect(screen.getByLabelText('Delete Can this bind CBD?')).toBeDisabled()
    sessionStorage.removeItem('bda_user')
  })

  it('shows the new status before the server answers', async () => {
    // Marking a goal answered is reversible and spends nothing, so the screen
    // does not wait for the round trip. The update is left unresolved here, so
    // anything visible is the optimistic value and nothing else.
    api.update.mockImplementation(() => new Promise(() => {}))
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    await screen.findByText('Can this bind CBD?')

    fireEvent.click(screen.getByRole('combobox', { name: 'Status of Can this bind CBD?' }))
    const answered = await screen.findByRole('option', { name: 'answered' })
    // The same pointer sequence the version test uses: this select commits on
    // pointer release, and a bare click selects nothing.
    fireEvent.pointerDown(answered, { button: 0 })
    fireEvent.pointerUp(answered, { button: 0 })
    fireEvent.click(answered)

    await waitFor(() => expect(api.update).toHaveBeenCalledWith('root', 1, { status: 'answered' }))
    expect(screen.getByRole('combobox', { name: 'Status of Can this bind CBD?' })).toHaveTextContent(
      'answered',
    )
  })

  it('puts the old status back when the write is refused', async () => {
    // A checkbox left showing a state the record does not have is worse than
    // one that never moved, so a rejection rolls the value back.
    api.update.mockRejectedValueOnce(new Error('Someone else answered this first'))
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    await screen.findByText('Can this bind CBD?')

    fireEvent.click(screen.getByRole('combobox', { name: 'Status of Can this bind CBD?' }))
    const answered = await screen.findByRole('option', { name: 'answered' })
    fireEvent.pointerDown(answered, { button: 0 })
    fireEvent.pointerUp(answered, { button: 0 })
    fireEvent.click(answered)

    // Asserted first, or this test would pass without anything having happened:
    // "still open" is also what a selection that never fired looks like.
    await waitFor(() => expect(api.update).toHaveBeenCalledWith('root', 1, { status: 'answered' }))
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Status of Can this bind CBD?' })).toHaveTextContent(
        'open',
      ),
    )
  })

  it('shows a retryable error rather than an empty goal tree on network failure', async () => {
    api.list.mockRejectedValueOnce(new Error('Goal service unavailable'))
    renderWithProviders(<ResearchGoalsPanel projectId="project-one" />)
    expect(await screen.findByText('Goal service unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})
