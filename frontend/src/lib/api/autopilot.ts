import {
  postStageReleaseApiV2AutopilotCampaignsCampaignIdStagesStageIdReleasePost,
  getCampaignApiV2AutopilotCampaignsCampaignIdGet,
  postCancelApiV2AutopilotCampaignsCampaignIdCancelPost,
  postConfirmApiV2AutopilotDraftsDraftIdConfirmPost,
  postDraftApiV2AutopilotDraftsPost,
  postStartApiV2AutopilotCampaignsCampaignIdStartPost,
  postTakeoverApiV2AutopilotCampaignsCampaignIdTakeoverPost,
} from './generated/sdk.gen'
import type {
  AutopilotCampaignResponse,
  AutopilotDraftResponse,
  AutopilotOperationAccepted,
} from './generated/types.gen'

export async function createAutopilotDraft(projectId: string, prompt: string) {
  const result = await postDraftApiV2AutopilotDraftsPost<true>({
    body: { project_id: projectId, prompt },
    throwOnError: true,
  })
  return {
    draft: result.data as AutopilotDraftResponse,
    etag: result.response.headers.get('etag') ?? 'W/"1"',
  }
}

export async function confirmAutopilotDraft(
  draftId: string,
  draftEtag: string,
  name: string,
  gpuSecondsLimit: number,
): Promise<AutopilotCampaignResponse> {
  const { data } = await postConfirmApiV2AutopilotDraftsDraftIdConfirmPost<true>({
    path: { draft_id: draftId },
    headers: { 'If-Match': draftEtag },
    body: {
      name,
      autonomy: 'supervised',
      budget: { gpu_seconds_limit: gpuSecondsLimit },
    },
    throwOnError: true,
  })
  return data
}

export async function startAutopilotCampaign(
  campaignId: string,
  gpuSeconds: number,
): Promise<AutopilotOperationAccepted> {
  const { data } = await postStartApiV2AutopilotCampaignsCampaignIdStartPost<true>({
    path: { campaign_id: campaignId },
    body: {
      idempotency_key: `ui-start-${campaignId}`,
      gpu_seconds: gpuSeconds,
      money_micros: 0,
    },
    throwOnError: true,
  })
  return data
}

export async function cancelAutopilotCampaign(campaignId: string): Promise<AutopilotOperationAccepted> {
  const { data } = await postCancelApiV2AutopilotCampaignsCampaignIdCancelPost<true>({
    path: { campaign_id: campaignId },
    throwOnError: true,
  })
  return data
}

export async function getAutopilotCampaign(campaignId: string): Promise<AutopilotCampaignResponse> {
  const { data } = await getCampaignApiV2AutopilotCampaignsCampaignIdGet<true>({
    path: { campaign_id: campaignId },
    throwOnError: true,
  })
  return data as AutopilotCampaignResponse
}

/** Take authority over a running campaign's products.
 *
 *  `If-Match` for the same reason every other mutation carries it: two people taking the
 *  same campaign over from two stale tabs must not both believe they did. A 412 here means
 *  reload and look again - the campaign moved, and the state you were acting on is gone.
 */
export async function takeOverAutopilotCampaign(
  campaignId: string,
  version: number,
): Promise<AutopilotCampaignResponse> {
  const { data } = await postTakeoverApiV2AutopilotCampaignsCampaignIdTakeoverPost<true>({
    path: { campaign_id: campaignId },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return data as AutopilotCampaignResponse
}

/**
 * Let one held stage act.
 *
 * Per stage rather than per campaign: `autonomy` is a dial with two positions, and a
 * campaign that asks about everything trains the reviewer to approve without reading.
 * What needs a person is decided by what the step does, so the approval is asked for where
 * that question is answerable.
 *
 * `If-Match` because two people releasing from two stale tabs must not both believe they
 * did. The server is idempotent, so a retry is not a second signature.
 */
export async function releaseAutopilotStage(campaignId: string, stageId: string, version: number) {
  const released = await postStageReleaseApiV2AutopilotCampaignsCampaignIdStagesStageIdReleasePost<true>({
    path: { campaign_id: campaignId, stage_id: stageId },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return released.data
}
