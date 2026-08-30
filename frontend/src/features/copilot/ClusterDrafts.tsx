import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  PlayIcon,
  SpinnerGapIcon,
  TerminalWindowIcon,
  ArrowsClockwiseIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import {
  confirmClusterDraft,
  getClusterDraft,
  listClusterDrafts,
  type ClusterDraft,
} from '../../lib/api/copilot'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Skeleton } from '../../components/ui/Skeleton'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FrameDescription, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { useI18n } from '../../lib/i18n'

function DraftPanel({ draft, readOnly }: { draft: ClusterDraft; readOnly: boolean }) {
  const { t, format } = useI18n()
  const queryClient = useQueryClient()
  const specification = draft.specification
  const queue = String(specification.queue ?? '')
  const cpuCount = Number(specification.cpu_count ?? 1)
  const gpuCount = Number(specification.gpu_count ?? 0)
  const script = String(specification.script ?? '')
  const confirm = useMutation({
    mutationFn: () => {
      if (readOnly) throw new Error(t.workflowExt.canvas.readOnlyBanner)
      return confirmClusterDraft(draft.id)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cluster-drafts'] }),
  })
  const refresh = useMutation({
    mutationFn: () => getClusterDraft(draft.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cluster-drafts'] }),
  })

  return (
    <FramePanel fit>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <strong className="text-sm text-foreground">{draft.name}</strong>
          <p className="text-xs text-muted-foreground">
            {queue} · {format(t.copilot.cluster.cpuGpu, { cpu: cpuCount, gpu: gpuCount })}
            {draft.confirmed_job_id ? ` · ${draft.confirmed_job_id}` : ''}
          </p>
        </div>
        <Badge variant="info-light" size="xs">
          {draft.status}
        </Badge>
      </div>
      {specification.rationale ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {String(specification.rationale)}
        </p>
      ) : null}
      {script ? (
        <Accordion className="mt-2">
          <AccordionItem value={`script-${draft.id}`}>
            <AccordionTrigger>{t.copilot.cluster.reviewScript}</AccordionTrigger>
            <AccordionContent>
              <pre className="whitespace-pre-wrap border bg-muted/40 p-2 font-mono text-[11px] text-muted-foreground">
                {script}
              </pre>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-2">
        {draft.status === 'draft' ? (
          <Button
            type="button"
            size="sm"
            disabled={readOnly || confirm.isPending}
            onClick={() => confirm.mutate()}
          >
            {confirm.isPending ? (
              <SpinnerGapIcon
                className="animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
            ) : (
              <PlayIcon aria-hidden="true" />
            )}
            {t.copilot.cluster.confirmSubmit}
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            <ArrowsClockwiseIcon
              className={refresh.isPending ? 'animate-spin motion-reduce:animate-none' : undefined}
              aria-hidden="true"
            />
            {t.copilot.cluster.refresh}
          </Button>
        )}
      </div>
      {confirm.isError ? (
        <Alert className="mt-2" variant="destructive">
          <WarningIcon aria-hidden="true" />
          <AlertDescription>
            {confirm.error instanceof Error ? confirm.error.message : t.copilot.cluster.submitFailed}
          </AlertDescription>
        </Alert>
      ) : null}
    </FramePanel>
  )
}

interface ClusterDraftsProps {
  projectId?: string
  variant?: 'drawer' | 'panel'
  readOnly?: boolean
}

export function ClusterDrafts({
  projectId,
  variant = 'panel',
  readOnly = false,
}: ClusterDraftsProps) {
  const { t } = useI18n()
  const [disclosure, setDisclosure] = useState<{
    projectId?: string
    openItems: string[]
    userInteracted: boolean
  }>({ projectId, openItems: [], userInteracted: false })
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cluster-drafts', projectId],
    queryFn: () => listClusterDrafts(projectId),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      return items.some((item) => ['submitted', 'queued', 'running'].includes(item.status))
        ? 5000
        : false
    },
  })
  const hasPending = data?.items.some((item) => item.status === 'draft') ?? false
  const activeDisclosure =
    disclosure.projectId === projectId
      ? disclosure
      : { projectId, openItems: [], userInteracted: false }
  const resolvedOpenItems =
    hasPending &&
    !activeDisclosure.userInteracted &&
    !activeDisclosure.openItems.includes('drafts')
      ? [...activeDisclosure.openItems, 'drafts']
      : activeDisclosure.openItems

  const body = (
    <Frame stacked dense className="mt-3">
      {isLoading ? (
        <>
          <FramePanel fit className="space-y-2">
            <Skeleton className="h-4 w-1/2 motion-reduce:animate-none" />
            <Skeleton className="h-3 w-4/5 motion-reduce:animate-none" />
          </FramePanel>
          <FramePanel fit className="space-y-2">
            <Skeleton className="h-4 w-2/3 motion-reduce:animate-none" />
            <Skeleton className="h-3 w-3/4 motion-reduce:animate-none" />
          </FramePanel>
        </>
      ) : null}
      {isError ? (
        <FramePanel fit>
          <Alert variant="destructive">
            <WarningIcon aria-hidden="true" />
            <AlertDescription>{t.copilot.cluster.loadFailed}</AlertDescription>
          </Alert>
        </FramePanel>
      ) : null}
      {!isLoading && !isError && data?.items.length
        ? data.items.map((item) => (
            <DraftPanel key={item.id} draft={item} readOnly={readOnly} />
          ))
        : null}
      {!isLoading && !isError && !data?.items.length ? (
        <FramePanel fit>
          <p className="text-xs text-muted-foreground">{t.copilot.cluster.empty}</p>
        </FramePanel>
      ) : null}
    </Frame>
  )

  const header = (
    <div>
      <div className="flex items-center gap-2">
        <TerminalWindowIcon className="size-4 text-primary" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-foreground">{t.copilot.cluster.title}</h3>
      </div>
      {variant === 'drawer' ? (
        <p className="mt-1 text-xs text-muted-foreground">{t.copilot.cluster.body}</p>
      ) : null}
    </div>
  )

  if (variant === 'panel') {
    return (
      <Frame dense>
        <FramePanel className="p-0">
          <Accordion
            value={resolvedOpenItems}
            onValueChange={(openItems) =>
              setDisclosure({ projectId, openItems, userInteracted: true })
            }
          >
            <AccordionItem value="drafts" className="border-0">
              <AccordionTrigger className="px-3 py-3">{header}</AccordionTrigger>
              <AccordionContent className="border-t p-3">
                {body}
                {data?.items.some((item) => item.status === 'completed') ? (
                  <p className="mt-3 inline-flex items-center gap-1 text-xs text-success">
                    <CheckCircleIcon aria-hidden="true" />
                    {t.copilot.cluster.completedOutputs}
                  </p>
                ) : null}
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </FramePanel>
      </Frame>
    )
  }

  return (
    <Frame spacing="sm">
      <FrameHeader>
        <FrameTitle>{header}</FrameTitle>
        <FrameDescription>{t.copilot.cluster.body}</FrameDescription>
      </FrameHeader>
      {body}
    </Frame>
  )
}
