import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamCopilotMessage } from './copilot'

describe('streamCopilotMessage', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.removeItem('bda_copilot_last_mode')
  })

  it('streams message chunks from SSE response body', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: message\ndata: hello\n\n'))
        controller.enqueue(encoder.encode('event: message\ndata: world\n\n'))
        controller.close()
      },
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(
        new Response(JSON.stringify({ conversation_id: 'conversation-1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ).mockResolvedValueOnce(
        new Response(body, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    const chunks: string[] = []
    await streamCopilotMessage({ project_id: 'project-1', messages: [{ role: 'user', content: 'hi' }] }, (chunk) => {
      chunks.push(chunk)
    })

    expect(chunks).toEqual(['hello', 'world'])
  })

  it('preserves a space-only message chunk from CRLF SSE framing', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: message\r\ndata: hello\r\n\r\n'))
        controller.enqueue(encoder.encode('event: message\r\ndata:  \r\n\r\n'))
        controller.enqueue(encoder.encode('event: message\r\ndata: world\r\n\r\n'))
        controller.close()
      },
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(
        new Response(JSON.stringify({ conversation_id: 'conversation-1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ).mockResolvedValueOnce(
        new Response(body, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    const chunks: string[] = []
    await streamCopilotMessage({ project_id: 'project-1', messages: [{ role: 'user', content: 'hi' }] }, (chunk) => {
      chunks.push(chunk)
    })

    expect(chunks).toEqual(['hello', ' ', 'world'])
    expect(chunks.join('')).toBe('hello world')
  })

  it('preserves tool status events from SSE response body', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: status\ndata: connected\n\n'))
        controller.enqueue(encoder.encode('event: status\ndata: thinking\n\n'))
        controller.enqueue(encoder.encode('event: status\ndata: tool:search_pdb\n\n'))
        controller.enqueue(encoder.encode('event: status\ndata: streaming\n\n'))
        controller.enqueue(encoder.encode('event: done\ndata: {"mode":"llm_with_tools"}\n\n'))
        controller.close()
      },
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(
        new Response(JSON.stringify({ conversation_id: 'conversation-1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ).mockResolvedValueOnce(
        new Response(body, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    const statuses: string[] = []
    await streamCopilotMessage(
      { project_id: 'project-1', messages: [{ role: 'user', content: 'find structures' }] },
      () => {},
      (status) => statuses.push(status),
    )

    expect(statuses).toEqual(['connecting', 'thinking', 'connecting', 'thinking', 'tool:search_pdb', 'streaming', 'done'])
    expect(sessionStorage.getItem('bda_copilot_last_mode')).toBeNull()
  })

  it('extracts assistant content and ignores the persisted user message', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: message\ndata: {"role":"user","content":"question"}\n\n'))
        controller.enqueue(encoder.encode('event: message\ndata: {"role":"assistant","content":"answer"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(new Response('{}', { status: 200 }))
        .mockResolvedValueOnce(new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })),
    )
    const chunks: string[] = []
    await streamCopilotMessage(
      { project_id: 'project-1', messages: [{ role: 'user', content: 'question' }] },
      (chunk) => chunks.push(chunk),
    )
    expect(chunks).toEqual(['answer'])
  })

  it('records acceptance before streaming and closes on done even if the server stays open', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: message\ndata: answer\n\nevent: done\ndata: {}\n\n'))
      },
      cancel,
    })
    const accepted = vi.fn()
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ conversation_id: 'c1', message: { id: 'm1' } }), { headers: { 'Content-Type': 'application/json' } }))
      .mockImplementationOnce(() => {
        expect(accepted).toHaveBeenCalledWith({ conversationId: 'c1', messageId: 'm1' })
        return Promise.resolve(new Response(body))
      }))
    const chunks = vi.fn()
    await expect(streamCopilotMessage(
      { project_id: 'p1', messages: [{ role: 'user', content: 'hi' }] }, chunks, undefined, undefined, accepted,
    )).resolves.toEqual({ conversationId: 'c1', messageId: 'm1' })
    expect(chunks).toHaveBeenCalledWith('answer')
    expect(cancel).toHaveBeenCalledOnce()
  })

  it('bounds a silent reply, aborts transport and cancels the reader without resubmitting', async () => {
    vi.useFakeTimers()
    const cancel = vi.fn()
    const body = new ReadableStream<Uint8Array>({ cancel })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ conversation_id: 'c1', message: { id: 'm1' } }), { headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(body))
    vi.stubGlobal('fetch', fetchMock)
    const result = streamCopilotMessage({ project_id: 'p1', messages: [{ role: 'user', content: 'hi' }] }, vi.fn())
    const assertion = expect(result).rejects.toThrow('copilot_wait_timeout')
    await vi.advanceTimersByTimeAsync(120_000)
    await assertion
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][1].signal.aborted).toBe(true)
    expect(cancel).toHaveBeenCalledOnce()
  })

  it('also bounds a stalled acceptance request', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn(() => new Promise<Response>(() => {}))
    vi.stubGlobal('fetch', fetchMock)
    const result = streamCopilotMessage({ project_id: 'p1', messages: [{ role: 'user', content: 'hi' }] }, vi.fn())
    const assertion = expect(result).rejects.toThrow('copilot_wait_timeout')
    await vi.advanceTimersByTimeAsync(120_000)
    await assertion
    expect(fetchMock).toHaveBeenCalledOnce()
  })
})
