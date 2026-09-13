import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/mocks/handlers'
import { defaultCopilotMessages, useAppStore } from '../../lib/store/appStore'
import { streamCopilotMessage } from '../../lib/api/copilot'
import type { CopilotChatRequest } from '../../lib/api/copilot'
import { CopilotChat } from './CopilotChat'

vi.mock('../../lib/api/copilot', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api/copilot')>()
  return {
    ...actual,
    streamCopilotMessage: vi.fn(async (_payload: CopilotChatRequest, onChunk: (text: string) => void) => {
      onChunk('Route context carried forward.')
      return { conversationId: 'conversation-test', messageId: 'message-test' }
    }),
    sendCopilotMessage: vi.fn(),
  }
})

function mockProjectContext(projectId = 'proj_test') {
  server.use(
    http.get('/api/v2/projects', () =>
      HttpResponse.json({
          items: [
            {
              id: projectId,
              organization_id: 'org_test',
              name: 'Test project',
              project_type: 'protein_design',
              status: 'active',
              owner_id: 'user_test',
              summary: 'Review test project',
              primary_target_id: null,
              version: 1,
              created_at: '2026-07-01T00:00:00Z',
              updated_at: '2026-07-01T00:00:00Z',
            },
          ],
          next_cursor: null,
      }),
    ),
  )
  useAppStore.setState({ activeProjectId: projectId })
}

describe('CopilotChat', () => {
  beforeEach(() => {
    mockProjectContext()
    useAppStore.setState({ copilotMessages: defaultCopilotMessages, copilotSessions: {}, language: 'en' })
    vi.mocked(streamCopilotMessage).mockImplementation(async (_payload, onChunk) => {
      onChunk('Route context carried forward.')
      return { conversationId: 'conversation-test', messageId: 'message-test' }
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('keeps one conversation across drawer/page remounts', async () => {
    const rendered = renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Plan the next protein workflow step' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => {
      expect(screen.getByText('Route context carried forward.')).toBeInTheDocument()
    })

    rendered.unmount()
    renderWithProviders(<CopilotChat pageContext="route=/results; project_id=proj_test" />)

    await waitFor(() => {
      expect(screen.getByText('Project proj_test')).toBeInTheDocument()
      expect(screen.getByText('Plan the next protein workflow step')).toBeInTheDocument()
      expect(screen.getByText('Route context carried forward.')).toBeInTheDocument()
    })
  })

  it('shows a readable failure reason when the Copilot request fails', async () => {
    vi.mocked(streamCopilotMessage).mockRejectedValueOnce(new Error('503 model unavailable'))
    renderWithProviders(<CopilotChat pageContext="route=/research; project_id=proj_test" />)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Show Botrytis research' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => {
      expect(screen.getByText('Copilot failed')).toBeInTheDocument()
      expect(screen.getAllByText(/model or backend service is temporarily unavailable/i).length).toBeGreaterThan(0)
    })
  })

  it('uses registry controls and one owning conversation scroll area', async () => {
    renderWithProviders(<CopilotChat pageContext="route=/research; project_id=proj_test" />)

    expect(screen.getByRole('textbox', { name: 'Ask the Copilot a question' })).toHaveAttribute(
      'data-slot',
      'input',
    )
    expect(screen.getByRole('button', { name: 'Send message' })).toHaveAttribute(
      'data-slot',
      'button',
    )
    expect(document.querySelectorAll('[data-slot="scroll-area"]')).toHaveLength(1)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Plan the next protein workflow step' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => {
      const reply = screen.getByText('Route context carried forward.')
      expect(reply.closest('[data-slot="frame-panel"]')).toBeInTheDocument()
      expect(reply).not.toHaveClass('max-h-[22rem]')
      expect(reply).not.toHaveClass('overflow-y-auto')
    })
  })

  it('does not submit Enter while an IME composition is active', async () => {
    renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    const input = screen.getByRole('textbox', { name: 'Ask the Copilot a question' })
    fireEvent.change(input, { target: { value: '蛋白质设计' } })
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })

    expect(streamCopilotMessage).not.toHaveBeenCalled()

    fireEvent.keyDown(input, { key: 'Enter', isComposing: false })
    await waitFor(() => expect(streamCopilotMessage).toHaveBeenCalledTimes(1))
  })

  it('localizes citation origins and secures external links', async () => {
    useAppStore.setState({
      language: 'zh',
      copilotMessages: [
        { role: 'user', content: '给出来源' },
        {
          role: 'assistant',
          content: '引用结果',
          meta: {
            citations: [
              {
                source_type: 'external',
                url: 'https://example.test/source',
              },
            ],
          },
        },
      ],
    })

    renderWithProviders(<CopilotChat pageContext="route=/research; project_id=proj_test" />)

    expect(await screen.findByText('引用结果')).toBeInTheDocument()
    const citation = await screen.findByRole('link')
    expect(citation).toHaveAccessibleName('来源 1 外部')
    expect(citation).toHaveAttribute('target', '_blank')
    expect(citation).toHaveAttribute('rel', expect.stringContaining('noopener'))
    expect(citation).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
    expect(citation.querySelector('[data-slot="badge"]')).toBeInTheDocument()
  })

  it('shows the active tool while Copilot is preparing a streamed answer', async () => {
    let finishStream: (() => void) | undefined
    vi.mocked(streamCopilotMessage).mockImplementationOnce(async (_payload, onChunk, onStatus) => {
      onStatus?.('tool:search_pdb')
      await new Promise<void>((resolve) => {
        finishStream = resolve
      })
      onChunk('Tool answer ready.')
      return { conversationId: 'conversation-test', messageId: 'message-test' }
    })
    renderWithProviders(<CopilotChat pageContext="route=/research; project_id=proj_test" />)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Search PDB structures for this target' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => {
      expect(screen.getByText('Using search pdb…')).toBeInTheDocument()
    })

    finishStream?.()
  })

  it('sanitizes persisted empty assistant placeholders before calling the API', async () => {
    useAppStore.setState({
      copilotMessages: [
        { role: 'user', content: 'Earlier question' },
        { role: 'assistant', content: '' },
      ],
    })

    renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Follow-up question' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => {
      expect(streamCopilotMessage).toHaveBeenCalled()
    })

    const payload = vi.mocked(streamCopilotMessage).mock.calls.at(-1)?.[0]
    expect(payload?.messages.every((message) => message.content.trim().length > 0)).toBe(true)
    expect(payload?.messages).toEqual(
      expect.arrayContaining([
        { role: 'user', content: 'Earlier question' },
        { role: 'user', content: 'Follow-up question' },
      ]),
    )
  })

  it('hides save-to-review on generic workflow chat', async () => {
    useAppStore.setState({
      copilotMessages: [
        { role: 'user', content: 'Explain candidate ranking' },
        { role: 'assistant', content: 'Candidate A is ranked first because of composite score.' },
      ],
    })

    renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)
    await waitFor(() => {
      expect(screen.getByText('Project proj_test')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: 'Save to project review' })).not.toBeInTheDocument()
  })

  it('shows save-to-review when a review section prompt was used', async () => {
    useAppStore.setState({
      copilotMessages: [
        {
          role: 'user',
          content: '请完善结合策略章节',
          meta: { reviewTrack: 'binding_strategy' },
        },
        { role: 'assistant', content: 'Binding strategy draft with supporting evidence.' },
      ],
    })

    renderWithProviders(<CopilotChat pageContext="route=/research; research_tab=evidence; project_id=proj_test" />)
    await waitFor(() => {
      expect(screen.getByText('Project proj_test')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Save to project review' })).toBeInTheDocument()
  })
  it('sends the selected bot instead of a matched skill, and only one of them', async () => {
    // The API rejects a request carrying both hints. This is where the two
    // could meet: an explicit pick, plus a message the skill matcher also
    // recognises.
    server.use(
      http.get('/api/v2/copilot/bots', () =>
        HttpResponse.json([
          {
            id: 'planner',
            title: 'Planner',
            title_zh: '路线规划',
            phase: 4,
            stance: 'produce',
            summary: 'Choose the route and draft the compute.',
            charter: 'Draft only; never confirm or submit.',
            capabilities: ['project-read', 'workflow-planning'],
            handoff: [],
            triggers: ['route'],
          },
        ]),
      ),
    )
    renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    fireEvent.click(await screen.findByRole('combobox', { name: 'Copilot bot' }))
    const planner = await screen.findByRole('option', { name: 'Planner' })
    fireEvent.pointerDown(planner, { button: 0 })
    fireEvent.pointerUp(planner, { button: 0 })
    fireEvent.click(planner)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Adjust the workflow threshold' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => expect(streamCopilotMessage).toHaveBeenCalled())
    const payload = vi.mocked(streamCopilotMessage).mock.calls.at(-1)?.[0]
    expect(payload?.bot).toBe('planner')
    expect(payload?.skill).toBeUndefined()
  })

  it('sends unhinted when the roster is unavailable', async () => {
    // The picker is absent and the chat still works. A roster that failed to
    // load must not take the copilot down with it.
    //
    // It used to fall back to a client-side skill guess here. That is gone with
    // the hand-written skill registry, and the change is a widening in this one
    // failure mode: the turn now carries no hint and gets the project's
    // configured set - the documented undifferentiated case, and the same thing
    // a message matching no trigger has always got. It is not a permission
    // change, because the server intersects whatever arrives with that set
    // either way; it is the loss of an incidental narrowing that only ever
    // applied when the roster request had failed.
    renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    fireEvent.change(screen.getByLabelText('Ask the Copilot a question'), {
      target: { value: 'Adjust the workflow threshold' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => expect(streamCopilotMessage).toHaveBeenCalled())
    const payload = vi.mocked(streamCopilotMessage).mock.calls.at(-1)?.[0]
    expect(payload?.bot).toBeUndefined()
    expect(payload?.skill).toBeUndefined()
    expect(screen.queryByRole('combobox', { name: 'Copilot bot' })).not.toBeInTheDocument()
  })
  it('shows the selected operator its charter, its reviewers and its reach', async () => {
    // All of this was on every roster response and none of it reached the
    // screen, which made selecting an operator a gesture rather than a decision.
    // `directs` was the last of them: the one operator whose whole job is
    // choosing another could not show which ones.
    server.use(
      http.get('/api/v2/copilot/bots', () =>
        HttpResponse.json([
          {
            id: 'conductor',
            title: 'Conductor',
            title_zh: '总调度',
            phase: -1,
            stance: 'direct',
            summary: 'Decide which operator works next.',
            charter: 'You route work; you do not do it.',
            capabilities: ['project-read'],
            handoff: ['auditor'],
            reviews: [],
            directs: ['planner'],
            reviewed_by: [],
            triggers: ['delegate'],
          },
          {
            id: 'planner',
            title: 'Planner',
            title_zh: '路线规划',
            phase: 4,
            stance: 'produce',
            summary: 'Choose the route.',
            charter: 'Draft only.',
            capabilities: ['project-read'],
            handoff: [],
            reviews: [],
            directs: [],
            reviewed_by: ['auditor'],
            triggers: ['route'],
          },
          {
            id: 'auditor',
            title: 'Auditor',
            title_zh: '复核',
            phase: 9,
            stance: 'review',
            summary: 'Judge claims.',
            charter: 'You judge claims; you never repair them.',
            capabilities: ['project-read'],
            handoff: [],
            reviews: ['planner'],
            directs: [],
            reviewed_by: [],
            triggers: ['verdict'],
          },
        ]),
      ),
    )
    renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    fireEvent.click(await screen.findByRole('combobox', { name: 'Copilot bot' }))
    const conductor = await screen.findByRole('option', { name: 'Conductor' })
    fireEvent.pointerDown(conductor, { button: 0 })
    fireEvent.pointerUp(conductor, { button: 0 })
    fireEvent.click(conductor)

    expect(await screen.findByText('You route work; you do not do it.')).toBeInTheDocument()
    expect(screen.getByText('May delegate to')).toBeInTheDocument()
    // ...and the named operator is a control, not prose: selecting it is the
    // action a reader wants next.
    expect(screen.getByRole('button', { name: 'Planner' })).toBeInTheDocument()
  })

  it('keeps the selected bot when the drawer is closed and reopened', async () => {
    // Component state sent the operator back to Auto every time the drawer
    // unmounted, with nothing on screen saying it had changed. conversationId
    // and messages already live in the project session; the bot belongs there
    // for the same reason.
    server.use(
      http.get('/api/v2/copilot/bots', () =>
        HttpResponse.json([
          {
            id: 'medic',
            title: 'Medic',
            title_zh: '故障诊断',
            phase: 6,
            stance: 'produce',
            summary: 'Explain why a job failed.',
            charter: 'You explain failures from recorded evidence.',
            capabilities: ['project-read', 'failure-diagnosis'],
            handoff: [],
            triggers: ['failed'],
          },
        ]),
      ),
    )
    const first = renderWithProviders(<CopilotChat pageContext="route=/workflow; project_id=proj_test" />)

    fireEvent.click(await screen.findByRole('combobox', { name: 'Copilot bot' }))
    const medic = await screen.findByRole('option', { name: 'Medic' })
    fireEvent.pointerDown(medic, { button: 0 })
    fireEvent.pointerUp(medic, { button: 0 })
    fireEvent.click(medic)
    await waitFor(() =>
      expect(useAppStore.getState().copilotSessions.proj_test?.bot).toBe('medic'),
    )

    first.unmount()
    renderWithProviders(<CopilotChat pageContext="route=/results; project_id=proj_test" />)

    fireEvent.change(await screen.findByLabelText('Ask the Copilot a question'), {
      target: { value: 'Why did it die?' },
    })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => expect(streamCopilotMessage).toHaveBeenCalled())
    expect(vi.mocked(streamCopilotMessage).mock.calls.at(-1)?.[0]?.bot).toBe('medic')
  })
})
