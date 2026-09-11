import './generatedTransport'
import {
  issueMcpSessionApiV2CopilotMcpSessionsPost,
  listMcpSessionsApiV2CopilotProjectsProjectIdMcpSessionsGet,
  revokeMcpSessionApiV2CopilotMcpSessionsSessionIdRevocationsPost,
} from './generated/sdk.gen'
import type { McpSessionIssued, McpSessionResponse } from './generated/types.gen'

/**
 * MCP sessions: one grant lets an external agent reach this project's copilot tools.
 *
 * The server decides what a grant can do on every call, never at issue time, so
 * `tools` and `write_tools` on a row are a reading of *now* - a project capability
 * switched off or a bound agent run that has finished both narrow an outstanding
 * grant without anyone revoking it. Nothing here caches that judgement.
 *
 * The raw token comes back exactly once, from `issueMcpSession`. Only its SHA-256
 * hash is stored, so a caller that drops it has to issue another grant; there is
 * no endpoint that can show it again and adding one would defeat hashing it.
 */

export type McpSession = McpSessionResponse
export type McpSessionGrant = McpSessionIssued

export async function listMcpSessions(projectId: string, limit = 50): Promise<McpSession[]> {
  const page = await listMcpSessionsApiV2CopilotProjectsProjectIdMcpSessionsGet<true>({
    path: { project_id: projectId },
    query: { limit },
    throwOnError: true,
  })
  return page.data.items
}

export async function issueMcpSession(body: {
  project_id: string
  label: string
  capabilities: string[]
  agent_run_id?: string | null
  expires_in_hours?: number
}): Promise<McpSessionGrant> {
  const issued = await issueMcpSessionApiV2CopilotMcpSessionsPost<true>({
    body,
    throwOnError: true,
  })
  return issued.data
}

export async function revokeMcpSession(sessionId: string, version: number): Promise<McpSession> {
  const revoked = await revokeMcpSessionApiV2CopilotMcpSessionsSessionIdRevocationsPost<true>({
    path: { session_id: sessionId },
    // Revoking is a mutation and carries the version, like every other one. A 412
    // here means the row moved — most likely someone else already revoked it, which
    // is worth reloading to see rather than overwriting.
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return revoked.data
}

/** Expired or revoked. Either way it can no longer authenticate. */
export function isSpent(session: McpSession, now: Date = new Date()): boolean {
  return session.revoked_at !== null || new Date(session.expires_at) <= now
}
