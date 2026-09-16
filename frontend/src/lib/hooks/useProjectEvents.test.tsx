import { act, cleanup, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { streamServerEvents } from '../api/sse'
import { useProjectEvents } from './useProjectEvents'
vi.mock('../api/sse', () => ({ streamServerEvents: vi.fn() }))
afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks() })
it('invalidates only the matching project, ignores repeated revisions, and aborts on switch', async () => {
  vi.mocked(streamServerEvents).mockImplementation(() => new Promise(() => {}))
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const { rerender, unmount } = renderHook(({ id }) => useProjectEvents(id), { wrapper, initialProps: { id: 'one' } })
  const options = vi.mocked(streamServerEvents).mock.calls[0][1]
  act(() => options.onEvent({ event: 'project-change', id: 'rev1', data: '{"project_id":"other"}' }))
  expect(invalidate).not.toHaveBeenCalled()
  act(() => options.onEvent({ event: 'project-change', id: 'rev1', data: '{"project_id":"one"}' }))
  expect(invalidate).toHaveBeenCalledTimes(6)
  act(() => options.onEvent({ event: 'project-change', id: 'rev1', data: '{"project_id":"one"}' }))
  expect(invalidate).toHaveBeenCalledTimes(6)
  rerender({ id: 'two' })
  expect(options.signal?.aborted).toBe(true)
  expect(vi.mocked(streamServerEvents).mock.calls[1][0]).toContain('/two/events')
  unmount()
  expect(vi.mocked(streamServerEvents).mock.calls[1][1].signal?.aborted).toBe(true)
})
it('keeps a timed fallback when a stream is silently buffered', () => {
  vi.useFakeTimers()
  vi.mocked(streamServerEvents).mockImplementation(() => new Promise(() => {}))
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  renderHook(() => useProjectEvents('one'), { wrapper })
  act(() => vi.advanceTimersByTime(30_000))
  expect(invalidate).toHaveBeenCalledTimes(6)
})
