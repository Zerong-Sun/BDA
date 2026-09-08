import { afterEach, describe, expect, it, vi } from 'vitest'
import { awaitOperation, isSettled, OperationFailed, OperationTimeout } from './operations'

const api = vi.hoisted(() => ({ get: vi.fn(), stream: vi.fn() }))

vi.mock('./sse', () => ({ streamServerEvents: api.stream }))

vi.mock('./generated/sdk.gen', () => ({
  getOperationApiV2OperationsOperationIdGet: api.get,
  listOperationsApiV2OperationsGet: vi.fn(),
}))

vi.mock('./generatedTransport', () => ({ generatedClient: {} }))

function operation(status: string, extra: Record<string, unknown> = {}) {
  return {
    data: {
      id: 'op-1',
      kind: 'experiment_results.import',
      status,
      result: {},
      error_message: null,
      ...extra,
    },
  }
}

describe('awaitOperation', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('polls even while the stream stays open without events', async () => {
    vi.useFakeTimers()
    api.stream.mockImplementation(() => new Promise(() => {}))
    api.get.mockResolvedValue(operation('succeeded'))
    const pending = awaitOperation('op-1', { intervalMs: 10, timeoutMs: 100 })
    await vi.advanceTimersByTimeAsync(10)
    expect(api.get).toHaveBeenCalledTimes(1)
    expect((await pending).status).toBe('succeeded')
    expect(api.stream.mock.calls[0][1].signal.aborted).toBe(true)
  })

  it('returns a terminal event without waiting for the stream to close', async () => {
    vi.useFakeTimers()
    api.stream.mockImplementation((_path, { onEvent }) => {
      onEvent({ event: 'operation', data: JSON.stringify(operation('succeeded').data) })
      return new Promise(() => {})
    })
    const result = vi.fn()
    void awaitOperation('op-1').then(result)
    await vi.advanceTimersByTimeAsync(0)
    expect(result).toHaveBeenCalledWith(operation('succeeded').data)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not start requests for an already aborted caller', async () => {
    const controller = new AbortController()
    controller.abort(new Error('navigation cancelled'))
    api.stream.mockRejectedValue(new Error('stream unavailable'))
    await expect(awaitOperation('op-1', { signal: controller.signal })).rejects.toThrow('navigation cancelled')
    expect(api.stream).not.toHaveBeenCalled()
    expect(api.get).not.toHaveBeenCalled()
  })

  it.each(['deadline', 'abort'])('bounds a hung poll by %s and aborts both requests', async (cause) => {
    vi.useFakeTimers()
    api.stream.mockImplementation(() => new Promise(() => {}))
    api.get.mockImplementation(() => new Promise(() => {}))
    const controller = new AbortController()
    const outcome = awaitOperation('op-1', {
      intervalMs: 10, timeoutMs: 100, signal: controller.signal,
    }).catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(10)
    if (cause === 'abort') controller.abort(new Error('navigation cancelled'))
    else await vi.advanceTimersByTimeAsync(90)
    const error = await outcome
    if (cause === 'abort') expect(String(error)).toContain('navigation cancelled')
    else expect(error).toBeInstanceOf(OperationTimeout)
    expect(api.get.mock.calls[0][0].signal.aborted).toBe(true)
    expect(api.stream.mock.calls[0][1].signal.aborted).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('settles from the stream without asking for the operation at all', async () => {
    api.stream.mockImplementation(async (_path: string, { onEvent }: { onEvent: (e: unknown) => void }) => {
      onEvent({ event: 'operation', data: JSON.stringify({ ...operation('succeeded').data, result: { imported: 3 } }) })
    })
    const settled = await awaitOperation('op-1')
    expect(settled.result).toEqual({ imported: 3 })
    expect(api.get).not.toHaveBeenCalled()
  })

  it('falls back to polling when the stream cannot open', async () => {
    // A buffering proxy or an idle timeout must not read as "the work is stuck".
    api.stream.mockRejectedValue(new Error('Stream failed to open (502)'))
    api.get.mockResolvedValue(operation('succeeded'))
    const settled = await awaitOperation('op-1', { intervalMs: 1 })
    expect(settled.status).toBe('succeeded')
    expect(api.get).toHaveBeenCalled()
  })

  it('falls back to polling when the stream ends without settling', async () => {
    api.stream.mockImplementation(async (_path: string, { onEvent }: { onEvent: (e: unknown) => void }) => {
      onEvent({ event: 'operation', data: JSON.stringify(operation('running').data) })
    })
    api.get.mockResolvedValue(operation('succeeded'))
    const settled = await awaitOperation('op-1', { intervalMs: 1 })
    expect(settled.status).toBe('succeeded')
  })

  it('returns as soon as the operation succeeds', async () => {
    api.stream.mockRejectedValue(new Error('no stream here'))
    api.get.mockResolvedValueOnce(operation('running')).mockResolvedValueOnce(
      operation('succeeded', { result: { imported: 7 } }),
    )
    const settled = await awaitOperation('op-1', { intervalMs: 1 })
    expect(settled.result).toEqual({ imported: 7 })
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('throws the failure with the server message, not a generic one', async () => {
    api.stream.mockRejectedValue(new Error('no stream here'))
    api.get.mockResolvedValue(operation('failed', { error_message: 'row 42 has no candidate' }))
    await expect(awaitOperation('op-1', { intervalMs: 1 })).rejects.toThrow('row 42 has no candidate')
    await expect(awaitOperation('op-1', { intervalMs: 1 })).rejects.toBeInstanceOf(OperationFailed)
  })

  it('hands a failure back instead of throwing when the caller renders it', async () => {
    // The import report is worth showing precisely when the import failed.
    api.stream.mockRejectedValue(new Error('no stream here'))
    api.get.mockResolvedValue(operation('failed', { error_message: 'bad header' }))
    const settled = await awaitOperation('op-1', { intervalMs: 1, settleOnFailure: true })
    expect(settled.status).toBe('failed')
  })

  it('times out saying the work is still running, because it is', async () => {
    api.stream.mockRejectedValue(new Error('no stream here'))
    api.get.mockResolvedValue(operation('running'))
    const error = await awaitOperation('op-1', { intervalMs: 1, timeoutMs: 5 }).catch((e) => e)
    expect(error).toBeInstanceOf(OperationTimeout)
    // Giving up watching is not the same as the work having stopped.
    expect(String(error)).toMatch(/still running/)
  })

  it('treats cancelled as settled', () => {
    expect(isSettled({ status: 'cancelled' })).toBe(true)
    expect(isSettled({ status: 'running' })).toBe(false)
  })
})
