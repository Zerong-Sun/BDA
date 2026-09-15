import { useQuery } from '@tanstack/react-query'
import {
  answerDecisionRequestApiV2CopilotDecisionRequestsRequestIdAnswersPost,
  listDecisionRequestsApiV2CopilotProjectsProjectIdDecisionRequestsGet,
  withdrawDecisionRequestApiV2CopilotDecisionRequestsRequestIdWithdrawalsPost,
} from '../../lib/api/generated'
import type { DecisionRequestResponse } from '../../lib/api/generated'

/**
 * The questions operators have put to a person.
 *
 * Answered ones are read too, and by default: a question and its answer are one
 * record, and a list that dropped the answered half would make the room's
 * history vanish the moment somebody acted on it. The inbox filters to `open`
 * because "what is waiting on me" is a different question from "what was
 * decided here".
 */

export const decisionRequestsQueryKey = (projectId: string | null, status?: string) =>
  ['copilot', 'decision-requests', projectId, status ?? 'all'] as const

export function useDecisionRequests(projectId: string | null, status?: 'open' | 'answered' | 'withdrawn') {
  return useQuery({
    queryKey: decisionRequestsQueryKey(projectId, status),
    enabled: Boolean(projectId),
    queryFn: async () => {
      const { data } = await listDecisionRequestsApiV2CopilotProjectsProjectIdDecisionRequestsGet<true>({
        throwOnError: true,
        path: { project_id: projectId as string },
        query: status ? { status } : {},
      })
      return data.items
    },
  })
}

/**
 * Settle one question.
 *
 * Carries the version as an ETag like every other mutation here: a 412 means
 * the question moved - another reviewer answered it, or the operator withdrew
 * it - and the client must reload rather than overwrite what happened.
 */
export async function answerDecisionRequest(
  requestId: string,
  version: number,
  choice: string,
  note = '',
): Promise<DecisionRequestResponse> {
  const { data } = await answerDecisionRequestApiV2CopilotDecisionRequestsRequestIdAnswersPost<true>({
    path: { request_id: requestId },
    body: { choice, note },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return data
}

/** Close a question the work moved past. Writes nothing to the record. */
export async function withdrawDecisionRequest(
  requestId: string,
  version: number,
): Promise<DecisionRequestResponse> {
  const { data } = await withdrawDecisionRequestApiV2CopilotDecisionRequestsRequestIdWithdrawalsPost<true>({
    path: { request_id: requestId },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return data
}
