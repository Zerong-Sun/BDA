import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusIcon, SpinnerGapIcon } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import {
  Frame,
  FrameDescription,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '../../components/reui/frame'
import {
  Timeline,
  TimelineContent,
  TimelineHeader,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from '../../components/reui/timeline'
import { Button } from '../../components/ui/Button'
import { ScrollArea } from '../../components/ui/scroll-area'
import {
  createCampaign,
  evaluateCampaignRound,
  getCampaign,
  listProjectCampaigns,
  reviewCampaignDecision,
  updateCampaignDecision,
  type Campaign,
} from '../../lib/api/campaigns'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { DecisionReview } from './DecisionReview'
import { jsonRecord, text } from './jsonHelpers'
import { localizeToken } from './researchUi'

export function CampaignPanel() {
  const { t, format } = useI18n()
  const c = t.research.campaign
  const client = useQueryClient()
  const { projectId } = useProjectContext()
  const campaigns = useQuery({
    queryKey: ['campaigns', projectId],
    queryFn: () => listProjectCampaigns(projectId),
    enabled: Boolean(projectId),
  })
  const [selected, setSelected] = useState('')
  const detail = useQuery({
    queryKey: ['campaign', selected],
    queryFn: () => getCampaign(selected),
    enabled: Boolean(selected),
    refetchInterval: 5000,
  })
  const create = useMutation({
    mutationFn: () => createCampaign({
      project_id: projectId,
      name: c.defaultName,
      objective: c.defaultObjective,
      max_rounds: 3,
      stop_conditions: [{ metric: 'experiments.bli.pass_rate', operator: '>=', value: 0.5, required: true }],
    }),
    onSuccess: (item) => {
      setSelected(item.id)
      client.invalidateQueries({ queryKey: ['campaigns', projectId] })
    },
  })
  const evaluate = useMutation({
    mutationFn: ({ id, round }: { id: string; round: number }) => evaluateCampaignRound(id, round),
    onSuccess: () => client.invalidateQueries({ queryKey: ['campaign', selected] }),
  })
  const review = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) => reviewCampaignDecision(id, approve),
    onSuccess: () => client.invalidateQueries({ queryKey: ['campaign', selected] }),
  })
  const updateDecision = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Record<string, unknown> }) =>
      updateCampaignDecision(id, patch, c.reviewedNote),
    onSuccess: () => client.invalidateQueries({ queryKey: ['campaign', selected] }),
  })

  const campaign = detail.data as Campaign | undefined
  const actionError = create.error || evaluate.error || review.error || updateDecision.error
  const decisionPending = updateDecision.isPending || review.isPending
  const mutationPending = create.isPending || evaluate.isPending || decisionPending

  return (
    <div className="grid min-h-0 gap-4 lg:h-[calc(100vh-12rem)] lg:grid-cols-[320px_1fr]">
      <Frame className="min-h-[24rem] lg:min-h-0" spacing="sm">
        <FramePanel className="flex min-h-0 flex-col">
          <Button
            type="button"
            className="w-full"
            disabled={!projectId || mutationPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <PlusIcon aria-hidden="true" />}
            {c.create}
          </Button>
          <ScrollArea className="mt-3 min-h-0 flex-1">
            <div className="grid gap-3 pr-2">
              {campaigns.data?.items.map((item) => {
                const maxRounds = jsonRecord(item.config).max_rounds
                return (
                  <Button
                    key={item.id}
                    type="button"
                    variant={selected === item.id ? 'secondary' : 'outline'}
                    className="h-auto w-full justify-start whitespace-normal p-3 text-left"
                    aria-pressed={selected === item.id}
                    onClick={() => setSelected(item.id)}
                  >
                    <span className="min-w-0">
                      <strong className="block truncate">{item.name}</strong>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {typeof maxRounds === 'number' ? `${format(c.round, { number: maxRounds })} · ` : ''}
                        {localizeToken(item.status, t.research.enums)}
                      </span>
                    </span>
                  </Button>
                )
              })}
            </div>
          </ScrollArea>
        </FramePanel>
      </Frame>

      <Frame className="min-h-[32rem] lg:min-h-0" spacing="sm">
        <FramePanel className="flex min-h-0 flex-col">
          {actionError ? (
            <Alert className="mb-3" variant="destructive">
              <AlertDescription>{actionError.message}</AlertDescription>
            </Alert>
          ) : null}
          {!campaign ? (
            <p className="text-muted-foreground">{c.selectOrCreate}</p>
          ) : (
            <>
              <FrameHeader>
                <FrameTitle>{campaign.name}</FrameTitle>
                <FrameDescription>{campaign.objective}</FrameDescription>
              </FrameHeader>
              <ScrollArea className="mt-3 min-h-0 flex-1">
                <Timeline
                  data-testid="campaign-rounds"
                  value={campaign.rounds?.filter((round) => round.status !== 'pending').length ?? 0}
                >
                  {campaign.rounds?.map((round) => {
                    const decision = round.decisions?.[0]
                    const decisionId = decision ? text(decision.id) : ''
                    const patch = decision?.parameter_patch
                    return (
                      <TimelineItem key={round.id} step={round.round_number}>
                        <TimelineIndicator />
                        <TimelineSeparator />
                        <TimelineHeader>
                          <TimelineTitle className="flex items-center justify-between gap-2">
                            <span>{format(c.round, { number: round.round_number })}</span>
                            <span className="flex flex-wrap gap-1">
                              <Badge variant="info-light" size="xs">
                                {localizeToken(round.status, t.research.enums)}
                              </Badge>
                              {decision ? (
                                <Badge variant="outline" size="xs">
                                  {localizeToken(decision.review_status, t.research.enums)}
                                </Badge>
                              ) : null}
                            </span>
                          </TimelineTitle>
                        </TimelineHeader>
                        <TimelineContent>
                          <p>{c.workflow} {round.workflow_run_id}</p>
                          {round.status === 'ready_for_evaluation' ? (
                            <Button
                              type="button"
                              className="mt-3"
                              variant="outline"
                              size="sm"
                              disabled={mutationPending}
                              onClick={() => evaluate.mutate({ id: campaign.id, round: round.round_number })}
                            >
                              {evaluate.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : null}
                              {c.evaluateRound}
                            </Button>
                          ) : null}
                          {decisionId && decision?.review_status === 'pending' ? (
                            <DecisionReview
                              key={`${decisionId}-${round.round_number}`}
                              decisionId={decisionId}
                              roundNumber={round.round_number}
                              patch={patch}
                              saving={mutationPending}
                              onSave={(id, nextPatch) => {
                                if (mutationPending) return Promise.resolve()
                                return updateDecision.mutateAsync({ id, patch: nextPatch })
                              }}
                              onReview={(id, approve) => {
                                if (mutationPending) return
                                review.mutate({ id, approve })
                              }}
                            />
                          ) : null}
                        </TimelineContent>
                      </TimelineItem>
                    )
                  })}
                </Timeline>
              </ScrollArea>
            </>
          )}
        </FramePanel>
      </Frame>
    </div>
  )
}
