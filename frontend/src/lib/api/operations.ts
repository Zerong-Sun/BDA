import './generatedTransport'
import {
  getOperationApiV2OperationsOperationIdGet,
  listOperationsApiV2OperationsGet,
} from './generated/sdk.gen'
import { streamServerEvents } from './sse'
import type { OperationResponse } from './generated/types.gen'

/**
 * Asynchronous work: what was queued, and where it got to.
 *
 * Every domain that queues something records an operation, and until the listing
 * endpoint existed there was no way to enumerate them - an operation was only ever a
 * local variable in whichever component started it, so navigating away lost the handle
 * to work that kept running.
 */

export type Operation = OperationResponse

/** Reached one of these and it will not change again. */
export const TERMINAL_OPERATION_STATUSES = ['succeeded', 'failed', 'cancelled'] as const

export function isSettled(operation: Pick<Operation, 'status'>): boolean {
  return (TERMINAL_OPERATION_STATUSES as readonly string[]).includes(operation.status)
}

export interface OperationQuery {
  projectId?: string
  kind?: string
  status?: string
  mine?: boolean
  /** ISO instant. Omitted means the server's default window, currently 30 days. */
  since?: string
  limit?: number
  cursor?: string
}

export async function listOperations(query: OperationQuery = {}) {
  const page = await listOperationsApiV2OperationsGet<true>({
    query: {
      limit: query.limit ?? 50,
      cursor: query.cursor,
      project_id: query.projectId,
      kind: query.kind || undefined,
      status: query.status || undefined,
      mine: query.mine || undefined,
      since: query.since,
    },
    throwOnError: true,
  })
  return page.data
}

export async function getOperation(operationId: string, signal?: AbortSignal): Promise<Operation> {
  const { data } = await getOperationApiV2OperationsOperationIdGet<true>({
    path: { operation_id: operationId },
    signal,
    throwOnError: true,
  })
  return data
}

export class OperationTimeout extends Error {}
export class OperationFailed extends Error {
  // Declared and assigned rather than a parameter property: the build runs with
  // `erasableSyntaxOnly`, which rejects the shorthand.
  readonly operation: Operation

  constructor(operation: Operation) {
    super(operation.error_message || `Operation ${operation.status}`)
    this.name = 'OperationFailed'
    this.operation = operation
  }
}

export interface AwaitOperationOptions {
  /** How long to keep asking before giving up. */
  timeoutMs?: number
  intervalMs?: number
  /** Return the failed operation instead of throwing, for callers that render it. */
  settleOnFailure?: boolean
  signal?: AbortSignal
}

/** Wait with streaming updates, independent polling, and a shared deadline. */
export async function awaitOperation(
  operationId: string,
  { timeoutMs = 180_000, intervalMs = 1_000, settleOnFailure = false, signal }: AwaitOperationOptions = {},
): Promise<Operation> {
  if (signal?.aborted) throw signal.reason ?? new Error('Aborted')
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || !Number.isFinite(intervalMs) || intervalMs <= 0) {
    throw new RangeError('Operation timeout and polling interval must be positive finite numbers')
  }
  return new Promise<Operation>((resolve, reject) => {
    const controller = new AbortController()
    let done = false
    let polling = false
    let latest: Operation | undefined
    let pollTimer: number | undefined
    const deadlineTimer = window.setTimeout(() => fail(new OperationTimeout(
      `${latest?.kind ?? 'Operation'} has not finished yet. It is still running — reopen Activity to check on it.`,
    )), timeoutMs)

    function cleanup() {
      done = true
      window.clearTimeout(deadlineTimer)
      window.clearTimeout(pollTimer)
      signal?.removeEventListener('abort', abort)
      controller.abort()
    }
    function fail(error: unknown) {
      if (done) return
      cleanup()
      reject(error)
    }
    function abort() {
      fail(signal?.reason ?? new Error('Aborted'))
    }
    function observe(operation: Operation) {
      if (done) return
      latest = operation
      if (!isSettled(operation)) return
      try {
        const result = finish(operation, settleOnFailure)
        cleanup()
        resolve(result)
      } catch (error) {
        fail(error)
      }
    }
    async function poll() {
      if (done || polling) return
      window.clearTimeout(pollTimer)
      polling = true
      try {
        observe(await getOperation(operationId, controller.signal))
      } catch (error) {
        fail(error)
      } finally {
        polling = false
        if (!done) pollTimer = window.setTimeout(() => void poll(), intervalMs)
      }
    }

    signal?.addEventListener('abort', abort, { once: true })
    pollTimer = window.setTimeout(() => void poll(), intervalMs)
    // A buffering proxy must not hold polling hostage. Stream termination only
    // accelerates the next poll; terminal events settle immediately while open.
    void streamServerEvents(`/operations/${operationId}/events`, {
      signal: controller.signal,
      onEvent: (event) => {
        if (event.event === 'operation') observe(JSON.parse(event.data) as Operation)
      },
    }).then(() => poll(), () => poll())
  })
}

function finish(operation: Operation, settleOnFailure: boolean): Operation {
  if (operation.status === 'succeeded' || settleOnFailure) return operation
  throw new OperationFailed(operation)
}
