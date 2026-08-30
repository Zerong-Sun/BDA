import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowSquareOutIcon,
  ChatCircleDotsIcon,
  CheckIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  SpinnerGapIcon,
  XIcon,
} from '@phosphor-icons/react'
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
  TimelineDate,
  TimelineHeader,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from '../../components/reui/timeline'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ScrollArea } from '../../components/ui/scroll-area'
import {
  createLiteratureSubscription,
  detectLiteratureRelations,
  ingestLiterature,
  listLiteratureClaims,
  listLiteratureRelations,
  listLiteratureSearches,
  listLiteratureSubscriptions,
  reviewLiteratureClaim,
  reviewLiteratureRelation,
  runLiteratureSubscription,
  searchLiteratureLibrary,
  updateLiteratureSubscription,
} from '../../lib/api/copilot'
import { getProjectResearchSummary } from '../../lib/api/projects'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { claimTitle, currentRole, jsonArray, jsonRecord, text } from './jsonHelpers'
import { projectLiteratureQuery } from './projectSearch'
import { SaveToReviewButton } from './SaveToReviewButton'
import {
  buildLiteratureClaimReviewContent,
  localizeToken,
  shouldAllowLiteratureReview,
  shouldOfferReviewPromotion,
} from './researchUi'

function documentLink(source: string, externalId: string | null): { href: string; label: string } | null {
  const id = externalId?.trim()
  if (!id) return null
  const kind = source.toLowerCase()
  if (id.startsWith('http')) return { href: id, label: id }
  if (kind.includes('doi') || id.startsWith('10.')) return { href: `https://doi.org/${id}`, label: id }
  if (kind.includes('pubmed') || kind.includes('pmid')) {
    return { href: `https://pubmed.ncbi.nlm.nih.gov/${id}/`, label: `PMID:${id}` }
  }
  return null
}

export function LiteraturePanel() {
  const { t, format, language } = useI18n()
  const l = t.research.literature
  const client = useQueryClient()
  const { activeProject, projectId } = useProjectContext()
  const setCopilotOpen = useAppStore((state) => state.setCopilotOpen)
  const role = currentRole()
  const isAdmin = role === 'admin'
  const canReview = shouldAllowLiteratureReview(role)
  const [query, setQuery] = useState('')
  const [openSections, setOpenSections] = useState<string[]>([])
  const autoQueryRef = useRef('')
  const projectIdRef = useRef('')
  const claims = useQuery({
    queryKey: ['literature-claims', projectId],
    queryFn: () => listLiteratureClaims(projectId),
    enabled: Boolean(projectId),
  })
  const projectResearch = useQuery({
    queryKey: ['project-research-summary', projectId],
    queryFn: () => getProjectResearchSummary(projectId),
    enabled: Boolean(projectId),
  })
  const relations = useQuery({
    queryKey: ['literature-relations', projectId],
    queryFn: () => listLiteratureRelations(projectId),
    enabled: Boolean(projectId),
  })
  const subscriptions = useQuery({
    queryKey: ['literature-subscriptions', projectId],
    queryFn: () => listLiteratureSubscriptions(projectId),
    retry: false,
    enabled: isAdmin && Boolean(projectId),
  })
  const search = useQuery({
    queryKey: ['literature-search', projectId, query],
    queryFn: () => searchLiteratureLibrary(projectId, query),
    enabled: false,
  })
  const searchRuns = useQuery({
    queryKey: ['literature-search-runs', projectId],
    queryFn: () => listLiteratureSearches(projectId),
    enabled: Boolean(projectId),
    refetchInterval: (request) => (
      request.state.data?.items.some((item) => ['pending', 'running'].includes(item.status)) ? 2000 : false
    ),
  })
  const defaultQuery = useMemo(
    () => projectLiteratureQuery(activeProject, projectResearch.data),
    [activeProject, projectResearch.data],
  )
  useEffect(() => {
    const projectChanged = projectIdRef.current !== projectId
    if (projectChanged || !query.trim() || query === autoQueryRef.current) {
      setQuery(defaultQuery)
      autoQueryRef.current = defaultQuery
    }
    projectIdRef.current = projectId
  }, [defaultQuery, projectId, query])

  const ingest = useMutation({
    mutationFn: () => ingestLiterature(projectId, query),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['literature-search-runs', projectId] })
      client.invalidateQueries({ queryKey: ['literature-claims', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
      search.refetch()
    },
  })
  const reviewClaim = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'accepted' | 'rejected' }) =>
      reviewLiteratureClaim(id, status),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['literature-claims', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const reviewRelation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'accepted' | 'rejected' }) =>
      reviewLiteratureRelation(id, status),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['literature-relations', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const detectRelations = useMutation({
    mutationFn: () => detectLiteratureRelations(projectId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['literature-relations', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const createSubscription = useMutation({
    mutationFn: () => createLiteratureSubscription(projectId, {
      name: query,
      query,
      enabled: true,
      interval_hours: 24,
      result_limit: 5,
      fetch_full_text: true,
      extract_claims: true,
    }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['literature-subscriptions', projectId] }),
  })
  const runSubscription = useMutation({
    mutationFn: runLiteratureSubscription,
    onSuccess: () => client.invalidateQueries({ queryKey: ['literature-subscriptions', projectId] }),
  })
  const toggleSubscription = useMutation({
    mutationFn: (item: NonNullable<typeof subscriptions.data>['items'][number]) =>
      updateLiteratureSubscription(item.subscription_id, {
        name: item.name,
        query: item.query,
        enabled: !item.enabled,
        interval_hours: item.interval_hours,
        result_limit: item.result_limit,
        fetch_full_text: item.fetch_full_text,
        extract_claims: item.extract_claims,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['literature-subscriptions', projectId] }),
  })

  const sourceRefs = jsonArray(jsonRecord(projectResearch.data?.brief?.scope).source_material) as Array<Record<string, unknown>>
  const referenceLinks = sourceRefs.flatMap((source) => jsonArray(source.references)).filter((item): item is string => typeof item === 'string')
  const claimTextById = useMemo(
    () => new Map((claims.data?.items ?? []).map((item) => [item.id, item.claim])),
    [claims.data?.items],
  )
  const writePending = ingest.isPending
    || reviewClaim.isPending
    || reviewRelation.isPending
    || detectRelations.isPending
    || createSubscription.isPending
    || runSubscription.isPending
    || toggleSubscription.isPending
  const visibleRuns = useMemo(
    () => [...(searchRuns.data?.items ?? [])]
      .sort((left, right) => (
        left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id)
      ))
      .slice(-10),
    [searchRuns.data?.items],
  )
  const firstIncompleteRun = visibleRuns.findIndex(
    (item) => ['pending', 'running'].includes(item.status),
  )
  const completedVisibleRunCount = firstIncompleteRun === -1 ? visibleRuns.length : firstIncompleteRun

  return (
    <div className="flex min-h-0 flex-col gap-4 lg:h-[calc(100vh-12rem)]">
      {referenceLinks.length ? (
        <Frame className="shrink-0" spacing="xs">
          <FramePanel>
            <Accordion
              value={openSections}
              onValueChange={setOpenSections}
              multiple
            >
              <AccordionItem value="linked-sources">
                <AccordionTrigger>
                  {format(l.viewLinkedSources, { count: referenceLinks.length })}
                </AccordionTrigger>
                {openSections.includes('linked-sources') ? (
                  <AccordionContent>
                    <div className="grid gap-1 md:grid-cols-2">
                      {referenceLinks.slice(0, 40).map((url) => (
                        <a
                          key={url}
                          className="inline-flex min-w-0 items-center gap-1 truncate text-xs text-primary hover:underline"
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ArrowSquareOutIcon aria-hidden="true" />
                          <span className="truncate">{url}</span>
                        </a>
                      ))}
                    </div>
                  </AccordionContent>
                ) : null}
              </AccordionItem>
            </Accordion>
          </FramePanel>
        </Frame>
      ) : null}

      <section className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <Frame className="min-h-[24rem] lg:min-h-0" spacing="sm">
          <FramePanel className="flex min-h-0 flex-col">
            <FrameHeader>
              <FrameTitle>{l.ingestionTitle}</FrameTitle>
              <FrameDescription>{l.ingestionBody}</FrameDescription>
            </FrameHeader>
            <div className="mt-3 flex flex-wrap gap-2">
              <Input
                className="min-w-72 flex-1"
                placeholder={activeProject ? l.searchPlaceholderActive : l.searchPlaceholderInactive}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <Button type="button" variant="outline" onClick={() => search.refetch()}>
                <MagnifyingGlassIcon aria-hidden="true" />{l.searchLocal}
              </Button>
              <Button type="button" disabled={!isAdmin || writePending} onClick={() => ingest.mutate()}>
                {ingest.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : null}
                {l.ingestNow}
              </Button>
              <Button type="button" variant="outline" disabled={!isAdmin || writePending} onClick={() => createSubscription.mutate()}>
                {l.createSurveillance}
              </Button>
              <Button type="button" variant="outline" onClick={() => setCopilotOpen(true)}>
                <ChatCircleDotsIcon aria-hidden="true" />{l.askCopilot}
              </Button>
            </div>
            {!isAdmin ? <Alert className="mt-2"><AlertDescription>{l.adminHint}</AlertDescription></Alert> : null}
            {ingest.isError || createSubscription.isError ? (
              <Alert className="mt-2" variant="destructive"><AlertDescription>{l.taskFailed}</AlertDescription></Alert>
            ) : null}
            <ScrollArea className="mt-3 min-h-0 flex-1">
              <div className="grid gap-3 pr-2">
                {visibleRuns.length ? (
                  <Timeline value={completedVisibleRunCount}>
                    {visibleRuns.map((run, index) => (
                      <TimelineItem key={run.id} step={index + 1}>
                        <TimelineIndicator />
                        <TimelineSeparator />
                        <TimelineHeader>
                          <TimelineDate>{run.created_at}</TimelineDate>
                          <TimelineTitle className="flex min-w-0 items-center justify-between gap-2">
                            <span className="truncate">Europe PMC · {run.query}</span>
                            <Badge variant="info-light" size="xs">{localizeToken(run.status, t.research.enums)}</Badge>
                          </TimelineTitle>
                        </TimelineHeader>
                        <TimelineContent>
                          {language === 'zh'
                            ? `检索留痕 ${run.result_count}/${run.requested_limit} · 开放全文 ${run.fetch_full_text ? '开启' : '关闭'}`
                            : `Trace retained · ${run.result_count}/${run.requested_limit} · open full text ${run.fetch_full_text ? 'on' : 'off'}`}
                          {run.error ? <Alert className="mt-2" variant="destructive"><AlertDescription>{run.error}</AlertDescription></Alert> : null}
                        </TimelineContent>
                      </TimelineItem>
                    ))}
                  </Timeline>
                ) : null}
                {search.data?.items.map((item) => {
                  const link = documentLink(item.source, item.external_id)
                  return (
                    <Frame key={item.id} spacing="xs">
                      <FramePanel>
                        <strong>{item.title}</strong>
                        <p className="mt-1 text-sm text-muted-foreground">{text(item.abstract) || l.ingestionBody}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{item.source}{item.external_id ? ` · ${item.external_id}` : ''}</p>
                        {item.metadata?.content_provenance && typeof item.metadata.content_provenance === 'object' ? (
                          <p className="mt-1 break-all text-[10px] text-muted-foreground">
                            {language === 'zh' ? '内容来源' : 'Content source'} · {text((item.metadata.content_provenance as Record<string, unknown>).content_kind)}
                            {' · SHA-256 '}{text((item.metadata.content_provenance as Record<string, unknown>).content_checksum_sha256).slice(0, 16)}
                            {' · trace '}{text((item.metadata.content_provenance as Record<string, unknown>).retrieval_trace_id).slice(0, 8)}
                          </p>
                        ) : null}
                        {link ? (
                          <a className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline" href={link.href} target="_blank" rel="noopener noreferrer">
                            <ArrowSquareOutIcon aria-hidden="true" />{link.label}
                          </a>
                        ) : null}
                      </FramePanel>
                    </Frame>
                  )
                })}
                {subscriptions.data?.items.map((item) => (
                  <Frame key={item.subscription_id} spacing="xs">
                    <FramePanel className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <strong className="block truncate">{item.name}</strong>
                        <p className="text-xs text-muted-foreground">{format(l.everyHours, { hours: item.interval_hours, nextRun: item.next_run_at })}</p>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button type="button" variant="outline" size="sm" disabled={writePending} onClick={() => toggleSubscription.mutate(item)}>
                          {item.enabled ? l.pause : l.enable}
                        </Button>
                        <Button type="button" variant="outline" size="sm" disabled={writePending} onClick={() => runSubscription.mutate(item.subscription_id)}>
                          <PlayIcon aria-hidden="true" />{l.runNow}
                        </Button>
                      </div>
                    </FramePanel>
                  </Frame>
                ))}
              </div>
            </ScrollArea>
          </FramePanel>
        </Frame>

        <div className="grid min-h-0 gap-4 lg:grid-rows-2">
          <Frame className="min-h-[20rem] lg:min-h-0" spacing="sm">
            <FramePanel className="flex min-h-0 flex-col">
              <FrameHeader><FrameTitle>{l.claimsTitle}</FrameTitle></FrameHeader>
              <ScrollArea className="mt-3 min-h-0 flex-1">
                <div className="grid gap-3 pr-2">
                  {claims.data?.items.map((item) => (
                    <Frame key={item.id} spacing="xs">
                      <FramePanel>
                        <strong>{claimTitle(item)}</strong>
                        <p className="mt-1 text-sm">{item.claim}</p>
                        {text(jsonRecord(item.attributes).evidence_excerpt) ? (
                          <blockquote className="mt-2 border-l-2 border-primary pl-2 text-xs text-muted-foreground">
                            {text(jsonRecord(item.attributes).evidence_excerpt)}
                          </blockquote>
                        ) : null}
                        <div className="mt-2 flex gap-2">
                          <Badge variant="info-light" size="xs">{localizeToken(item.confidence, t.research.enums)}</Badge>
                          <Badge variant="outline" size="xs">{localizeToken(item.review_status, t.research.enums)}</Badge>
                        </div>
                        <div className="mt-2 flex gap-2">
                          <Button type="button" variant="outline" size="sm" disabled={!canReview || writePending} onClick={() => reviewClaim.mutate({ id: item.id, status: 'accepted' })}>
                            <CheckIcon aria-hidden="true" />{t.shared.accept}
                          </Button>
                          <Button type="button" variant="destructive" size="sm" disabled={!canReview || writePending} onClick={() => reviewClaim.mutate({ id: item.id, status: 'rejected' })}>
                            <XIcon aria-hidden="true" />{t.shared.reject}
                          </Button>
                        </div>
                        {!canReview ? <p className="mt-2 text-xs text-muted-foreground">{l.reviewPermissionHint}</p> : null}
                        {projectId && shouldOfferReviewPromotion(text(item.review_status)) ? (
                          <SaveToReviewButton
                            projectId={projectId}
                            content={buildLiteratureClaimReviewContent(item)}
                            reviewTrack="references_reading"
                          />
                        ) : null}
                      </FramePanel>
                    </Frame>
                  ))}
                </div>
              </ScrollArea>
              {reviewClaim.isError ? <Alert className="mt-3" variant="destructive"><AlertDescription>{l.reviewFailed}</AlertDescription></Alert> : null}
            </FramePanel>
          </Frame>

          <Frame className="min-h-[20rem] lg:min-h-0" spacing="sm">
            <FramePanel className="flex min-h-0 flex-col">
              <FrameHeader className="flex-row items-center justify-between">
                <FrameTitle>{l.relationsTitle}</FrameTitle>
                <Button type="button" variant="outline" size="sm" disabled={!isAdmin || writePending} onClick={() => detectRelations.mutate()}>
                  {l.detectRelations}
                </Button>
              </FrameHeader>
              <ScrollArea className="mt-3 min-h-0 flex-1">
                <div className="grid gap-3 pr-2">
                  {relations.data?.items.map((item) => (
                    <Frame key={item.id} spacing="xs">
                      <FramePanel>
                        <Badge variant="info-light" size="xs">{localizeToken(item.relation_type, t.research.enums)}</Badge>
                        <p className="mt-2 text-sm">{claimTextById.get(item.source_claim_id) ?? item.source_claim_id}</p>
                        <p className="text-sm text-muted-foreground">↔ {claimTextById.get(item.target_claim_id) ?? item.target_claim_id}</p>
                        {item.rationale ? <p className="mt-1 text-sm text-muted-foreground">{item.rationale}</p> : null}
                        <div className="mt-2 flex gap-2">
                          <Button type="button" variant="outline" size="sm" disabled={!canReview || writePending} onClick={() => reviewRelation.mutate({ id: item.id, status: 'accepted' })}>
                            <CheckIcon aria-hidden="true" />{t.shared.accept}
                          </Button>
                          <Button type="button" variant="destructive" size="sm" disabled={!canReview || writePending} onClick={() => reviewRelation.mutate({ id: item.id, status: 'rejected' })}>
                            <XIcon aria-hidden="true" />{t.shared.reject}
                          </Button>
                        </div>
                        {!canReview ? <p className="mt-2 text-xs text-muted-foreground">{l.reviewPermissionHint}</p> : null}
                      </FramePanel>
                    </Frame>
                  ))}
                </div>
              </ScrollArea>
              {reviewRelation.isError ? <Alert className="mt-3" variant="destructive"><AlertDescription>{l.reviewFailed}</AlertDescription></Alert> : null}
            </FramePanel>
          </Frame>
        </div>
      </section>
    </div>
  )
}
