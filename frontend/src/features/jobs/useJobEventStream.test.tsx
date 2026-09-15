import type { ReactNode } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MAX_JOB_STREAMS, useJobEventStream } from './useJobEventStream'

/**
 * The hook is a hint layer over polling, so the tests are about the ways a
 * hint layer goes wrong: watching only one of several live jobs, opening a
 * connection per job without limit, tearing down healthy streams when the
 * caller re-renders, and reporting "streaming" when nothing is connected.
 */

const sse = vi.hoisted(() => ({ stream: vi.fn() }))

vi.mock('../../lib/api/sse', () => ({ streamServerEvents: sse.stream }))

afterEach(() => {
  sse.stream.mockReset()
})

// A flag rather than an optional `runId` with a default: a default parameter
// replaces an explicit `undefined`, so "no run" could not be expressed at all.
function mount(jobIds: string[], { withoutRun = false }: { withoutRun?: boolean } = {}) {
  const runId = withoutRun ? undefined : 'run-1'
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const view = renderHook(({ ids }: { ids: string[] }) => useJobEventStream(ids, runId), {
    wrapper,
    initialProps: { ids: jobIds },
  })
  return { ...view, client }
}

/** A stream that stays open, the way a healthy one does. */
function pending() {
  sse.stream.mockImplementation(() => new Promise(() => {}))
}

function urls() {
  return sse.stream.mock.calls.map((call) => call[0] as string)
}

describe('useJobEventStream', () => {
  it('watches every job that is still moving, not only the first', () => {
    pending()

    mount(['job-a', 'job-b', 'job-c'])

    expect(urls()).toEqual([
      '/jobs/job-a/events',
      '/jobs/job-b/events',
      '/jobs/job-c/events',
    ])
  })

  it('caps how many connections it opens at once', () => {
    pending()

    mount(Array.from({ length: 12 }, (_index, i) => `job-${i}`))

    // A browser allows about six per host; past the cap the extra connections
    // would queue and report nothing while looking live.
    expect(urls()).toHaveLength(MAX_JOB_STREAMS)
  })

  it('does not reopen streams when the caller re-renders with an equal list', () => {
    pending()
    const { rerender } = mount(['job-a', 'job-b'])

    rerender({ ids: ['job-a', 'job-b'] })
    rerender({ ids: ['job-b', 'job-a'] })

    expect(sse.stream).toHaveBeenCalledTimes(2)
  })

  it('opens nothing without a workflow run', () => {
    pending()

    const { result } = mount(['job-a'], { withoutRun: true })

    expect(sse.stream).not.toHaveBeenCalled()
    expect(result.current).toBe(false)
  })

  it('reports streaming while connected, and stops reporting it when the stream ends', async () => {
    let finish: (() => void) | undefined
    sse.stream.mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))

    const { result } = mount(['job-a'])

    await waitFor(() => expect(result.current).toBe(true))
    await act(async () => {
      finish?.()
    })
    await waitFor(() => expect(result.current).toBe(false))
  })

  it('a refused stream leaves the caller on its own polling rather than erroring', async () => {
    sse.stream.mockImplementation(() => Promise.reject(new Error('502')))

    const { result } = mount(['job-a'])

    await waitFor(() => expect(result.current).toBe(false))
  })

  it('an event refreshes the job list, that job’s logs and the canvas', async () => {
    // Captured rather than fired during mount, so the assertion is about what
    // an event does and not about what mounting does.
    let emit: (() => void) | undefined
    sse.stream.mockImplementation((_path: string, options: { onEvent: (event: unknown) => void }) => {
      emit = () => options.onEvent({ event: 'status', data: '{}' })
      return new Promise(() => {})
    })
    const { client } = mount(['job-a'])
    const invalidated: unknown[] = []
    vi.spyOn(client, 'invalidateQueries').mockImplementation((filters) => {
      invalidated.push(filters?.queryKey)
      return Promise.resolve()
    })

    await waitFor(() => expect(emit).toBeDefined())
    act(() => emit?.())

    expect(invalidated).toEqual([
      ['workflow-jobs', 'run-1'],
      ['job-logs', 'job-a'],
      ['workflow-graph', 'run-1'],
    ])
  })
})
