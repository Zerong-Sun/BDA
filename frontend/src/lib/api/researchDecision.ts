import './generatedTransport'
import { patchResearchGoalApiV2ResearchGoalsGoalIdPatch } from './generated/sdk.gen'
import type { ResearchDecisionContract } from './generated/types.gen'

export async function updateResearchDecision(goalId: string, version: number, contract: ResearchDecisionContract) {
  return (await patchResearchGoalApiV2ResearchGoalsGoalIdPatch<true>({
    path: { goal_id: goalId }, headers: { 'If-Match': `W/"${version}"` },
    body: { decision_contract: contract }, throwOnError: true,
  })).data
}
