import { afterEach, expect, it, vi } from 'vitest'
import { streamServerEvents } from './sse'

vi.mock('./client', () => ({ API_BASE: '/api/v2', authToken: () => null }))

afterEach(() => vi.unstubAllGlobals())

it('cancels the response body when a consumer stops on an event', async () => {
  const cancel = vi.fn()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('event: operation\ndata: {"status":"succeeded"}\n\n'))
    },
    cancel,
  })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)))
  await expect(streamServerEvents('/events', {
    onEvent() { throw new Error('consumer stopped') },
  })).rejects.toThrow('consumer stopped')
  expect(cancel).toHaveBeenCalledOnce()
  expect(body.locked).toBe(false)
})

it('decodes fragmented UTF-8 and CRLF frames and releases the completed body', async () => {
  const bytes = new TextEncoder().encode('event: update\r\ndata: 测试\r\ndata: second\r\n\r\n')
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
      controller.close()
    },
  })
  const onEvent = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)))
  await streamServerEvents('/events', { onEvent })
  expect(onEvent).toHaveBeenCalledExactlyOnceWith({ event: 'update', data: '测试\nsecond', id: undefined })
  expect(body.locked).toBe(false)
})
