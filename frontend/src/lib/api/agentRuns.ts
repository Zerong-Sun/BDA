import './generatedTransport'
import {
  cancelAgentRunApiV2CopilotAgentRunsRunIdCancellationsPost,
  getAgentRunApiV2CopilotAgentRunsRunIdGet,
  listAgentRunsApiV2CopilotProjectsProjectIdAgentRunsGet,
  listAgentTurnsApiV2CopilotAgentRunsRunIdTurnsGet,
  startAgentRunApiV2CopilotAgentRunsPost,
} from './generated/sdk.gen'
import type { AgentRunResponse, AgentTurnResponse } from './generated/types.gen'

/**
 * Durable agent runs.
 *
 * A run outlives the request that starts it, so nothing here waits for a
 * result: `startAgentRun` returns as soon as the run exists, and the transcript
 * is read afterwards. That is the same shape as chat, for the same reason.
 */

export type AgentRun = AgentRunResponse
export type AgentTurn = AgentTurnResponse

/** States a run can still move from. Everything else is final. */
export const LIVE_RUN_STATUSES = ['running', 'awaiting_tasks'] as const

export function isLive(run: Pick<AgentRun, 'status'>): boolean {
  return (LIVE_RUN_STATUSES as readonly string[]).includes(run.status)
}

export async function startAgentRun(body: {
  project_id: string
  goal: string
  skills?: string[]
  max_turns?: number
  max_cost_usd_cents?: number | null
}) {
  const accepted = await startAgentRunApiV2CopilotAgentRunsPost<true>({
    body,
    throwOnError: true,
  })
  return accepted.data
}

export async function listAgentRuns(projectId: string, limit = 50) {
  const page = await listAgentRunsApiV2CopilotProjectsProjectIdAgentRunsGet<true>({
    path: { project_id: projectId },
    query: { limit },
    throwOnError: true,
  })
  return page.data.items
}

export async function getAgentRun(runId: string) {
  const run = await getAgentRunApiV2CopilotAgentRunsRunIdGet<true>({
    path: { run_id: runId },
    throwOnError: true,
  })
  return run.data
}

export async function listAgentTurns(runId: string, limit = 200) {
  const page = await listAgentTurnsApiV2CopilotAgentRunsRunIdTurnsGet<true>({
    path: { run_id: runId },
    query: { limit },
    throwOnError: true,
  })
  return page.data.items
}

export async function cancelAgentRun(runId: string, version: number) {
  const cancelled = await cancelAgentRunApiV2CopilotAgentRunsRunIdCancellationsPost<true>({
    path: { run_id: runId },
    // Cancelling is a mutation, so it carries the version as an ETag; a 412
    // means the run moved on its own and the client must reload before deciding
    // again — by then it may have finished without help.
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return cancelled.data
}
