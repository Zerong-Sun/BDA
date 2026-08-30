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

export async function getOperation(operationId: string): Promise<Operation> {
  const { data } = await getOperationApiV2OperationsOperationIdGet<true>({
    path: { operation_id: operationId },
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

/**
 * Watch the operation stream until it settles, or give up so the caller can poll.
 *
 * Resolves with the settled operation, or with null when the stream could not carry
 * the answer - it failed to open, dropped, or the environment has no streaming body.
 * Null is not an error: polling is the floor underneath this, and treating a dropped
 * connection as a failed operation would be a lie about the work.
 */
async function watchOperation(
  operationId: string,
  timeoutMs: number,
  signal: AbortSignal | undefined,
): Promise<Operation | null> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort)
  const giveUp = window.setTimeout(abort, timeoutMs)
  let settled: Operation | null = null
  try {
    await streamServerEvents(`/operations/${operationId}/events`, {
      signal: controller.signal,
      onEvent: (event) => {
        if (event.event !== 'operation') return
        const operation = JSON.parse(event.data) as Operation
        if (isSettled(operation)) settled = operation
      },
    })
  } catch {
    return null
  } finally {
    window.clearTimeout(giveUp)
    signal?.removeEventListener('abort', abort)
  }
  if (signal?.aborted) throw signal.reason ?? new Error('Aborted')
  return settled
}

/**
 * Wait for an operation to settle.
 *
 * This replaced three hand-rolled loops that each had their own cadence, their own
 * timeout and their own wording for the same event - 60x500ms, 30x1000ms and
 * 180x1000ms, in two files. Callers differ only in how long they are willing to wait
 * and whether a failure is an exception or a result to render.
 *
 * The stream is tried first and polling is the floor beneath it, rather than the
 * stream replacing polling. A server-sent stream has more ways to not arrive than a
 * request does - a proxy that buffers, an idle timeout, a corporate middlebox - and
 * every one of them would otherwise read to the user as "my import is stuck" when the
 * import is fine.
 */
export async function awaitOperation(
  operationId: string,
  { timeoutMs = 180_000, intervalMs = 1_000, settleOnFailure = false, signal }: AwaitOperationOptions = {},
): Promise<Operation> {
  const deadline = Date.now() + timeoutMs
  const streamed = await watchOperation(operationId, timeoutMs, signal)
  if (streamed) return finish(streamed, settleOnFailure)

  for (;;) {
    if (signal?.aborted) throw signal.reason ?? new Error('Aborted')
    const operation = await getOperation(operationId)
    if (isSettled(operation)) return finish(operation, settleOnFailure)
    if (Date.now() + intervalMs > deadline) {
      throw new OperationTimeout(
        `${operation.kind} has not finished yet. It is still running — reopen Activity to check on it.`,
      )
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs))
  }
}

function finish(operation: Operation, settleOnFailure: boolean): Operation {
  if (operation.status === 'succeeded' || settleOnFailure) return operation
  throw new OperationFailed(operation)
}
