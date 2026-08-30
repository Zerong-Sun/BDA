import './generatedTransport'
import {
  getCampaignApiV2CampaignsCampaignIdGet,
  getDecisionApiV2CampaignDecisionsDecisionIdGet,
  listCampaignsApiV2ProjectsProjectIdCampaignsGet,
  listDecisionsApiV2CampaignRoundsRoundIdDecisionsGet,
  listEvaluationsApiV2CampaignRoundsRoundIdEvaluationsGet,
  listRoundsApiV2CampaignsCampaignIdRoundsGet,
  patchDecisionApiV2CampaignDecisionsDecisionIdPatch,
  postCampaignApiV2ProjectsProjectIdCampaignsPost,
  reviewDecisionApiV2CampaignDecisionsDecisionIdReviewPost,
  runRoundEvaluationApiV2CampaignRoundsRoundIdEvaluationRunsPost,
} from './generated/sdk.gen'
import type { CampaignResponse, DecisionResponse, EvaluationResponse, RoundResponse } from './generated/types.gen'

export interface Campaign extends CampaignResponse {
  rounds?: Array<RoundResponse & { evaluations: EvaluationResponse[]; decisions: DecisionResponse[] }>
}

export interface CreateCampaignPayload {
  project_id: string
  name: string
  objective: string
  initial_workflow_run_id?: string
  max_rounds?: number
  budget?: Record<string, unknown>
  stop_conditions?: Array<Record<string, unknown>>
  strategy?: Record<string, unknown>
}

export function createCampaign(payload: CreateCampaignPayload): Promise<CampaignResponse> {
  return postCampaignApiV2ProjectsProjectIdCampaignsPost<true>({
    path: { project_id: payload.project_id },
    body: { name: payload.name, objective: payload.objective,
      config: { max_rounds: payload.max_rounds, budget: payload.budget,
        stop_conditions: payload.stop_conditions, strategy: payload.strategy } },
    throwOnError: true,
  }).then((response) => response.data)
}

export function listProjectCampaigns(projectId: string) {
  return listCampaignsApiV2ProjectsProjectIdCampaignsGet<true>({
    path: { project_id: projectId }, query: { limit: 200 }, throwOnError: true,
  }).then((response) => response.data)
}

export async function getCampaign(campaignId: string): Promise<Campaign> {
  const [campaignResponse, roundsResponse] = await Promise.all([
    getCampaignApiV2CampaignsCampaignIdGet<true>({ path: { campaign_id: campaignId }, throwOnError: true }),
    listRoundsApiV2CampaignsCampaignIdRoundsGet<true>({
      path: { campaign_id: campaignId }, query: { limit: 200 }, throwOnError: true,
    }),
  ])
  const rounds = await Promise.all(roundsResponse.data.items.map(async (round) => {
    const [evaluations, decisions] = await Promise.all([
      listEvaluationsApiV2CampaignRoundsRoundIdEvaluationsGet<true>({
        path: { round_id: round.id }, query: { limit: 200 }, throwOnError: true,
      }),
      listDecisionsApiV2CampaignRoundsRoundIdDecisionsGet<true>({
        path: { round_id: round.id }, query: { limit: 200 }, throwOnError: true,
      }),
    ])
    return { ...round, evaluations: evaluations.data.items, decisions: decisions.data.items }
  }))
  return { ...campaignResponse.data, rounds }
}

export async function evaluateCampaignRound(campaignId: string, roundNumber: number) {
  const rounds = await listRoundsApiV2CampaignsCampaignIdRoundsGet<true>({
    path: { campaign_id: campaignId }, query: { limit: 200 }, throwOnError: true,
  })
  const round = rounds.data.items.find((item) => item.round_number === roundNumber)
  if (!round) throw new Error('Campaign round was not found')
  return runRoundEvaluationApiV2CampaignRoundsRoundIdEvaluationRunsPost<true>({
    path: { round_id: round.id }, throwOnError: true,
  }).then((response) => response.data)
}

export async function updateCampaignDecision(decisionId: string, parameterPatch: Record<string, unknown>, rationale?: string) {
  const current = await getDecisionApiV2CampaignDecisionsDecisionIdGet<true>({
    path: { decision_id: decisionId }, throwOnError: true,
  })
  return patchDecisionApiV2CampaignDecisionsDecisionIdPatch<true>({
    path: { decision_id: decisionId }, headers: { 'If-Match': `W/"${current.data.version}"` },
    body: { parameter_patch: parameterPatch, rationale }, throwOnError: true,
  }).then((response) => response.data)
}

export async function reviewCampaignDecision(decisionId: string, approve: boolean) {
  const current = await getDecisionApiV2CampaignDecisionsDecisionIdGet<true>({
    path: { decision_id: decisionId }, throwOnError: true,
  })
  return reviewDecisionApiV2CampaignDecisionsDecisionIdReviewPost<true>({
    path: { decision_id: decisionId }, headers: { 'If-Match': `W/"${current.data.version}"` },
    body: { approve }, throwOnError: true,
  }).then((response) => response.data)
}
