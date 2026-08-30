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
})
