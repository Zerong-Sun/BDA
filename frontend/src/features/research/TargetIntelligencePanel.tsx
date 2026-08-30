import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import {
  ArrowSquareOutIcon,
  CheckIcon,
  CrosshairIcon,
  DownloadSimpleIcon,
  FileTextIcon,
  GitBranchIcon,
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
  TimelineHeader,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from '../../components/reui/timeline'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import { ScrollArea } from '../../components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { Textarea } from '../../components/ui/textarea'
import {
  buildTargetEvidenceReviewContent,
  localizeToken,
  shouldAllowTargetEvidenceReview,
  shouldOfferReviewPromotion,
} from './researchUi'
import {
  advanceTargetIntelligenceRun,
  analyzeTargetIntelligence,
  applyTargetDesignRoute,
  exportTargetDossier,
  getTargetIntelligenceRun,
  reviewTargetEvidence,
  reviewTargetHotspot,
  type TargetDesignRoute,
} from '../../lib/api/copilot'
import { fetchPdb } from '../../lib/api/targets'
import { confirmTargetIdentity } from '../../lib/api/projects'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useProjectTargetStructure } from '../../lib/hooks/useProjectTargetStructure'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import {
  parseHotspotResidue,
  structureSourceFromTarget,
  structureSourceFromUrl,
} from '../pdb-viewer/types'
import { useI18n } from '../../lib/i18n'
import { SaveToReviewButton } from './SaveToReviewButton'

function metadataId(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key]
  return typeof value === 'string' ? value : ''
}

export function TargetIntelligencePanel() {
  const { t, format } = useI18n()
  const ti = t.research.targetIntelligence
  const client = useQueryClient()
  const { projectId } = useProjectContext()
  const [targetQuery, setTargetQuery] = useState('')
  const [objective, setObjective] = useState('')
  const [modality, setModality] = useState('auto')
  const [organism, setOrganism] = useState('')
  const [constructStart, setConstructStart] = useState('')
  const [constructEnd, setConstructEnd] = useState('')
  const [selectedRoute, setSelectedRoute] = useState('')
  const [exportPreview, setExportPreview] = useState('')
  const [structurePreviewUrl, setStructurePreviewUrl] = useState<string | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [openSupport, setOpenSupport] = useState<string[]>(['source-status', 'agent-steps'])
  const projectTarget = useProjectTargetStructure(projectId)

  const analyze = useMutation({
    mutationFn: () => analyzeTargetIntelligence({
      project_id: projectId || undefined,
      target_query: targetQuery,
      objective,
      modality,
      organism: organism.trim() || undefined,
    }),
    onSuccess: (report) => {
      setSelectedRoute(report.design_routes[0]?.route_id ?? '')
      setExportPreview('')
      if (report.run_id) {
        client.invalidateQueries({ queryKey: ['target-intelligence-run', report.run_id] })
      }
    },
  })
  const runId = analyze.data?.run_id ?? ''
  const runDetail = useQuery({
    queryKey: ['target-intelligence-run', runId],
    queryFn: () => getTargetIntelligenceRun(runId),
    enabled: Boolean(runId),
  })
  const report = runDetail.data?.report ?? analyze.data
  const confirmIdentity = useMutation({
    mutationFn: () => {
      if (!projectId || !report) throw new Error('project_and_target_required')
      return confirmTargetIdentity(projectId, {
        target_name: report.target.name,
        uniprot_accession: report.target.uniprot_accession ?? undefined,
        organism: report.target.organism ?? undefined,
        construct_start: constructStart ? Number(constructStart) : undefined,
        construct_end: constructEnd ? Number(constructEnd) : undefined,
      })
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['target-readiness', projectId] })
      client.invalidateQueries({ queryKey: ['project-target-structure', projectId] })
      client.invalidateQueries({ queryKey: ['project-overview', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const highlightedResidues =
    report?.hotspots
      ?.map((hotspot) => parseHotspotResidue(hotspot.residue, hotspot.chain_id, hotspot.residue_index))
      .filter((item): item is NonNullable<typeof item> => item != null) ?? []
  const selected = report?.design_routes.find((route) => route.route_id === selectedRoute) ?? report?.design_routes[0]
  const sourceStatuses = Object.entries(report?.audit.source_status ?? {})
  const agentSteps = report?.audit.agent_steps ?? []
  const allowEvidenceReview = shouldAllowTargetEvidenceReview(report?.stage)
  const reviewGateSatisfied = report?.stage === 'evidence_review'
    ? report.evidence.length > 0
      && report.evidence.every((item) => ['accepted', 'rejected'].includes(item.review_status))
      && report.evidence.some((item) => item.review_status === 'accepted')
    : report?.stage === 'hotspot_review'
      ? report.hotspots.every((item) => ['confirmed', 'rejected'].includes(item.status))
      : true
  const refreshRun = (updatedReport?: { design_routes?: TargetDesignRoute[] }) => {
    const nextRoute = updatedReport?.design_routes?.[0]?.route_id
    if (nextRoute) setSelectedRoute(nextRoute)
    if (runId) client.invalidateQueries({ queryKey: ['target-intelligence-run', runId] })
    client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
  }
  const advanceRun = useMutation({
    mutationFn: () => advanceTargetIntelligenceRun(runId),
    onSuccess: refreshRun,
  })
  const reviewEvidence = useMutation({
    mutationFn: ({ evidenceItemId, status }: { evidenceItemId: string; status: 'accepted' | 'rejected' }) =>
      reviewTargetEvidence(runId, evidenceItemId, status),
    onSuccess: refreshRun,
  })
  const reviewHotspot = useMutation({
    mutationFn: ({ hotspotId, status }: { hotspotId: string; status: 'confirmed' | 'rejected' }) =>
      reviewTargetHotspot(runId, hotspotId, { status }),
    onSuccess: refreshRun,
  })
  const applyRoute = useMutation({
    mutationFn: (route: TargetDesignRoute) => applyTargetDesignRoute(runId, {
      route_id: route.route_id,
      selected_module_ids: route.module_ids,
    }),
    onSuccess: () => {
      if (runId) client.invalidateQueries({ queryKey: ['target-intelligence-run', runId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const fetchStructure = useMutation({
    mutationFn: (pdbId: string) => {
      if (!projectId) throw new Error('project_required')
      return fetchPdb(pdbId, projectId)
    },
    onSuccess: () => {
      setFetchError(null)
      setStructurePreviewUrl(null)
      if (projectId) {
        client.invalidateQueries({ queryKey: ['project-target-structure', projectId] })
        client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
      }
    },
    onError: () => setFetchError(ti.fetchStructureFailed),
  })
  const exportDossier = useMutation({
    mutationFn: (exportFormat: 'json' | 'markdown') => exportTargetDossier(runId, exportFormat),
    onSuccess: (payload) => setExportPreview(payload.content),
  })

  const downloadPreview = () => {
    if (!exportDossier.data) return
    const blob = new Blob([exportDossier.data.content], { type: exportDossier.data.media_type })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = exportDossier.data.filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const mutationPending = analyze.isPending
    || confirmIdentity.isPending
    || advanceRun.isPending
    || reviewEvidence.isPending
    || reviewHotspot.isPending
    || applyRoute.isPending
    || fetchStructure.isPending
    || exportDossier.isPending
  const viewerHeight = report ? 240 : 360
  const completedAgentSteps = agentSteps.filter((step) => step.status === 'completed').length

  return (
    <div className="grid min-h-0 gap-4 lg:h-[calc(100vh-12rem)] lg:grid-cols-[360px_1fr]">
      <Frame className="min-h-[32rem] lg:min-h-0" spacing="sm">
        <FramePanel className="flex min-h-0 flex-col">
          <FrameHeader>
            <p className="text-xs uppercase tracking-wide text-primary">{ti.eyebrow}</p>
            <FrameTitle><h2>{ti.title}</h2></FrameTitle>
            <FrameDescription>{ti.body}</FrameDescription>
          </FrameHeader>
          <div className="mt-4 grid gap-3">
            <div className="grid gap-1">
              <Label htmlFor="target-intelligence-target">{ti.targetLabel}</Label>
              <Input
                id="target-intelligence-target"
                placeholder={ti.targetPlaceholder}
                value={targetQuery}
                onChange={(event) => setTargetQuery(event.target.value)}
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="target-intelligence-objective">{ti.objectiveLabel}</Label>
              <Textarea
                id="target-intelligence-objective"
                className="min-h-24"
                placeholder={ti.objectivePlaceholder}
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="target-intelligence-modality">{ti.modalityLabel}</Label>
              <Select value={modality} onValueChange={(value) => setModality(value ?? 'auto')}>
                <SelectTrigger id="target-intelligence-modality" className="w-full" aria-label={ti.modalityLabel}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">{ti.modalityAuto}</SelectItem>
                  <SelectItem value="binder">{ti.modalityBinder}</SelectItem>
                  <SelectItem value="antibody">{ti.modalityAntibody}</SelectItem>
                  <SelectItem value="peptide">{ti.modalityPeptide}</SelectItem>
                  <SelectItem value="scaffold_redesign">{ti.modalityScaffoldRedesign}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1">
              <Label htmlFor="target-intelligence-organism">{ti.organismLabel}</Label>
              <Input
                id="target-intelligence-organism"
                placeholder={ti.organismPlaceholder}
                value={organism}
                onChange={(event) => setOrganism(event.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-1">
                <Label htmlFor="target-intelligence-start">{ti.constructStart}</Label>
                <Input id="target-intelligence-start" type="number" min="1" value={constructStart} onChange={(event) => setConstructStart(event.target.value)} />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="target-intelligence-end">{ti.constructEnd}</Label>
                <Input id="target-intelligence-end" type="number" min="1" value={constructEnd} onChange={(event) => setConstructEnd(event.target.value)} />
              </div>
            </div>
            <Button type="button" disabled={!targetQuery.trim() || !objective.trim() || mutationPending} onClick={() => analyze.mutate()}>
              {analyze.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <CrosshairIcon aria-hidden="true" />}
              {ti.analyze}
            </Button>
          </div>
          {analyze.isError ? <Alert className="mt-3" variant="destructive"><AlertDescription>{ti.analyzeFailed}</AlertDescription></Alert> : null}
          {runDetail.isFetching ? <p className="mt-3 text-xs text-muted-foreground" role="status">{ti.analyze}</p> : null}
          {report ? (
            <Frame className="mt-4" spacing="xs">
              <FramePanel>
                <strong>{report.target.name}</strong>
                <p className="mt-1 text-xs text-muted-foreground">{report.target.organism ?? ti.organismUnresolved} · {report.target.uniprot_accession ?? ti.uniprotUnresolved}</p>
                <p className="mt-2 text-xs text-muted-foreground">{report.target.construct_recommendation}</p>
                <Button type="button" className="mt-3" variant="outline" size="sm" disabled={!projectId || mutationPending || !report.target.name} onClick={() => confirmIdentity.mutate()}>
                  {confirmIdentity.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <CheckIcon aria-hidden="true" />}
                  {ti.confirmIdentity}
                </Button>
                {confirmIdentity.isSuccess ? <Alert className="mt-2" variant="success"><AlertDescription>{ti.identityConfirmed}</AlertDescription></Alert> : null}
                {confirmIdentity.isError ? <Alert className="mt-2" variant="destructive"><AlertDescription>{ti.identityConfirmFailed}</AlertDescription></Alert> : null}
                <div className="mt-3 flex flex-wrap items-start gap-2">
                  <Badge variant="info-light" size="xs">{localizeToken(report.stage, t.research.enums)}</Badge>
                  {report.stage !== 'completed' && report.stage !== 'failed' ? (
                    <div className="grid gap-1">
                      <Button type="button" variant="outline" size="sm" disabled={!runId || mutationPending || !reviewGateSatisfied} onClick={() => advanceRun.mutate()}>
                        {advanceRun.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : null}
                        {ti.advance}
                      </Button>
                      <p className="text-[11px] text-muted-foreground">{ti.reviewBeforeAdvance}</p>
                    </div>
                  ) : null}
                </div>
              </FramePanel>
            </Frame>
          ) : null}

          <ScrollArea className="mt-4 min-h-0 flex-1">
            <Accordion value={openSupport} onValueChange={setOpenSupport} multiple className="pr-2">
              <AccordionItem value="evidence-levels">
                <AccordionTrigger>{ti.evidenceLevels}</AccordionTrigger>
                {openSupport.includes('evidence-levels') ? (
                  <AccordionContent>
                    <dl className="grid gap-1 text-xs text-muted-foreground">
                      {([
                        ['A', ti.evidenceA],
                        ['B', ti.evidenceB],
                        ['C', ti.evidenceC],
                        ['D', ti.evidenceD],
                      ] as const).map(([level, meaning]) => (
                        <div key={level} className="grid grid-cols-[1.75rem_1fr] gap-2">
                          <dt className="font-semibold text-foreground">{level}</dt><dd>{meaning}</dd>
                        </div>
                      ))}
                    </dl>
                  </AccordionContent>
                ) : null}
              </AccordionItem>
              <AccordionItem value="glossary">
                <AccordionTrigger>{ti.glossary}</AccordionTrigger>
                {openSupport.includes('glossary') ? (
                  <AccordionContent>
                    <dl className="grid gap-2 text-xs text-muted-foreground">
                      {([
                        [ti.glossaryHotspotTerm, ti.glossaryHotspot],
                        [ti.glossaryEpitopeTerm, ti.glossaryEpitope],
                        [ti.glossaryRouteTerm, ti.glossaryRoute],
                        [ti.glossaryRegexTerm, ti.glossaryRegex],
                      ] as const).map(([term, meaning]) => <div key={term}><dt className="font-semibold text-foreground">{term}</dt><dd>{meaning}</dd></div>)}
                    </dl>
                  </AccordionContent>
                ) : null}
              </AccordionItem>
              {sourceStatuses.length ? (
                <AccordionItem value="source-status">
                  <AccordionTrigger>{ti.sourceStatus}</AccordionTrigger>
                  {openSupport.includes('source-status') ? (
                    <AccordionContent>
                      <div className="grid gap-1">
                        {sourceStatuses.map(([source, status]) => (
                          <p key={source} className="flex items-center justify-between gap-2">
                            <span className="capitalize">{source.replaceAll('_', ' ')}</span>
                            <Badge variant={status.status === 'failed' ? 'destructive-light' : 'outline'} size="xs">
                              {localizeToken(status.status, t.research.enums)}{status.item_count != null ? ` · ${status.item_count}` : ''}
                            </Badge>
                          </p>
                        ))}
                      </div>
                    </AccordionContent>
                  ) : null}
                </AccordionItem>
              ) : null}
              {agentSteps.length ? (
                <AccordionItem value="agent-steps">
                  <AccordionTrigger>{ti.agentSteps}</AccordionTrigger>
                  {openSupport.includes('agent-steps') ? (
                    <AccordionContent>
                      <Timeline value={completedAgentSteps}>
                        {agentSteps.map((step, index) => (
                          <TimelineItem key={`${step.role}-${step.stage}-${step.summary}`} step={index + 1}>
                            <TimelineIndicator />
                            <TimelineSeparator />
                            <TimelineHeader>
                              <TimelineTitle>{step.role}</TimelineTitle>
                            </TimelineHeader>
                            <TimelineContent>
                              <Badge variant="outline" size="xs">{localizeToken(step.stage, t.research.enums)}</Badge>
                              <p className="mt-1">{step.summary}</p>
                            </TimelineContent>
                          </TimelineItem>
                        ))}
                      </Timeline>
                    </AccordionContent>
                  ) : null}
                </AccordionItem>
              ) : null}
            </Accordion>
            <div className="grid gap-2 pr-2">
              {report?.audit.limitations.map((item) => (
                <Alert key={item} variant="warning"><AlertDescription>{item}</AlertDescription></Alert>
              ))}
            </div>
          </ScrollArea>
        </FramePanel>
      </Frame>

      <section
        className="grid min-h-0 content-start gap-4 lg:overflow-y-auto lg:pr-1"
        data-testid="target-intelligence-detail"
      >
        <Frame spacing="sm">
          <FramePanel>
            <FrameHeader><FrameTitle>{ti.structurePreview}</FrameTitle></FrameHeader>
            {projectTarget.data ? (
              <StructureViewerLazy source={structureSourceFromTarget(projectTarget.data, projectId || undefined, { highlightedResidues })} height={viewerHeight} />
            ) : structurePreviewUrl ? (
              <StructureViewerLazy source={structureSourceFromUrl(structurePreviewUrl, { projectId: projectId || undefined, highlightedResidues })} height={viewerHeight} />
            ) : (
              <Alert><AlertDescription>{t.viewer.proteinNoStructure}</AlertDescription></Alert>
            )}
          </FramePanel>
        </Frame>

        <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <Frame className="min-h-[24rem] lg:min-h-0" spacing="sm">
            <FramePanel className="flex min-h-0 flex-col">
              <FrameHeader className="flex-row items-center justify-between">
                <FrameTitle className="flex items-center gap-2"><FileTextIcon aria-hidden="true" />{ti.evidenceTitle}</FrameTitle>
                <Badge variant="outline" size="xs">{format(ti.items, { count: report?.evidence.length ?? 0 })}</Badge>
              </FrameHeader>
              <ScrollArea className="mt-3 min-h-0 flex-1">
                <div className="grid gap-3 pr-2">
                  {report?.evidence.map((item, index) => {
                    const evidenceItemId = metadataId(item.metadata, 'evidence_item_id')
                    return (
                      <Frame key={`${item.source_type}-${item.identifier ?? index}`} spacing="xs">
                        <FramePanel>
                          <div className="flex items-start justify-between gap-2">
                            <strong>{item.title}</strong>
                            <div className="flex shrink-0 gap-1">
                              <Badge variant="info-light" size="xs">{item.evidence_level}</Badge>
                              <Badge variant="outline" size="xs">{localizeToken(item.review_status, t.research.enums)}</Badge>
                            </div>
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">{item.claim}</p>
                          {item.excerpt ? <blockquote className="mt-2 border-l-2 border-primary pl-2 text-xs text-muted-foreground">{item.excerpt}</blockquote> : null}
                          {item.url ? (
                            <a className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline" href={item.url} target="_blank" rel="noopener noreferrer">
                              <ArrowSquareOutIcon aria-hidden="true" />{item.identifier ?? item.source_type}
                            </a>
                          ) : <p className="mt-2 text-xs text-muted-foreground">{item.identifier ?? item.source_type}</p>}
                          {item.source_type === 'pdb' && item.identifier && projectId ? (
                            <Button type="button" className="mt-2" variant="outline" size="sm" disabled={mutationPending} onClick={() => fetchStructure.mutate(item.identifier!.slice(0, 4).toUpperCase())}>
                              {fetchStructure.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : null}{ti.fetchStructure}
                            </Button>
                          ) : null}
                          {allowEvidenceReview && evidenceItemId ? (
                            <div className="mt-3 flex gap-2">
                              <Button type="button" variant="outline" size="sm" disabled={mutationPending} onClick={() => reviewEvidence.mutate({ evidenceItemId, status: 'accepted' })}>
                                <CheckIcon aria-hidden="true" />{t.shared.accept}
                              </Button>
                              <Button type="button" variant="destructive" size="sm" disabled={mutationPending} onClick={() => reviewEvidence.mutate({ evidenceItemId, status: 'rejected' })}>
                                <XIcon aria-hidden="true" />{t.shared.reject}
                              </Button>
                            </div>
                          ) : null}
                          {projectId && shouldOfferReviewPromotion(item.review_status) ? (
                            <SaveToReviewButton projectId={projectId} content={buildTargetEvidenceReviewContent(item)} reviewTrack="target_mechanism_structure" />
                          ) : null}
                        </FramePanel>
                      </Frame>
                    )
                  })}
                  {!report ? <Alert><AlertDescription>{ti.emptyEvidence}</AlertDescription></Alert> : null}
                </div>
              </ScrollArea>
              {reviewEvidence.isError ? <Alert className="mt-3" variant="destructive"><AlertDescription>{ti.evidenceReviewFailed}</AlertDescription></Alert> : null}
              {fetchError ? <Alert className="mt-3" variant="destructive"><AlertDescription>{fetchError}</AlertDescription></Alert> : null}
            </FramePanel>
          </Frame>

          <div className="grid min-h-0 gap-4 lg:grid-rows-2">
            <Frame className="min-h-[14rem] lg:min-h-0" spacing="sm">
              <FramePanel className="flex min-h-0 flex-col">
                <FrameHeader><FrameTitle>{ti.hotspotsTitle}</FrameTitle></FrameHeader>
                <ScrollArea className="mt-3 min-h-0 flex-1">
                  <div className="grid gap-2 pr-2">
                    {report?.hotspots.map((item) => {
                      const hotspotId = metadataId(item.metadata, 'hotspot_id')
                      return (
                        <Frame key={`${item.residue}-${item.region}`} spacing="xs">
                          <FramePanel>
                            <div className="flex items-center justify-between gap-2"><strong>{item.residue}</strong><Badge variant="info-light" size="xs">{item.region}</Badge></div>
                            <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                              {localizeToken(item.status, t.research.enums)} · {item.extraction_method?.replaceAll('_', ' ') ?? ti.methodPending}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">{item.rationale}</p>
                            {report.stage === 'hotspot_review' && hotspotId ? (
                              <div className="mt-3 flex gap-2">
                                <Button type="button" variant="outline" size="sm" disabled={mutationPending} onClick={() => reviewHotspot.mutate({ hotspotId, status: 'confirmed' })}><CheckIcon aria-hidden="true" />{ti.confirm}</Button>
                                <Button type="button" variant="destructive" size="sm" disabled={mutationPending} onClick={() => reviewHotspot.mutate({ hotspotId, status: 'rejected' })}><XIcon aria-hidden="true" />{t.shared.reject}</Button>
                              </div>
                            ) : null}
                          </FramePanel>
                        </Frame>
                      )
                    })}
                  </div>
                </ScrollArea>
              </FramePanel>
            </Frame>
            <Frame className="min-h-[14rem] lg:min-h-0" spacing="sm">
              <FramePanel className="flex min-h-0 flex-col">
                <FrameHeader><FrameTitle>{ti.validationPlanTitle}</FrameTitle></FrameHeader>
                <ScrollArea className="mt-3 min-h-0 flex-1">
                  <div className="grid gap-2 pr-2 text-xs text-muted-foreground">
                    {report ? [
                      ...report.experiment_plan.binding_validation,
                      ...report.experiment_plan.specificity,
                      ...report.experiment_plan.developability,
                      ...report.experiment_plan.mutation_or_epitope_validation,
                    ].map((item) => <Frame key={item} spacing="xs"><FramePanel>{item}</FramePanel></Frame>) : null}
                  </div>
                </ScrollArea>
              </FramePanel>
            </Frame>
          </div>
        </div>

        <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <Frame className="min-h-[20rem] lg:min-h-0" spacing="sm">
            <FramePanel className="flex min-h-0 flex-col">
              <FrameHeader className="flex-row items-center justify-between">
                <FrameTitle className="flex items-center gap-2"><GitBranchIcon aria-hidden="true" />{ti.designRoutesTitle}</FrameTitle>
                <Button type="button" disabled={!selected || !runId || report?.stage !== 'completed' || mutationPending} onClick={() => selected && applyRoute.mutate(selected)}>
                  {applyRoute.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : null}{ti.createWorkflow}
                </Button>
              </FrameHeader>
              <ScrollArea className="mt-3 min-h-0 flex-1">
                <div className="grid gap-3 pr-2">
                  {report?.design_routes.map((route) => (
                    <Button
                      key={route.route_id}
                      type="button"
                      variant={selectedRoute === route.route_id ? 'secondary' : 'outline'}
                      className="h-auto w-full justify-start whitespace-normal p-3 text-left"
                      aria-pressed={selectedRoute === route.route_id}
                      onClick={() => setSelectedRoute(route.route_id)}
                    >
                      <span className="min-w-0">
                        <span className="flex items-start justify-between gap-2"><strong>{route.label}</strong><Badge variant="outline" size="xs">{route.fit}</Badge></span>
                        <span className="mt-1 block text-xs text-muted-foreground">{route.rationale}</span>
                        <span className="mt-2 block text-[10px] uppercase tracking-wide text-primary">{route.methods.join(' · ')}</span>
                      </span>
                    </Button>
                  ))}
                </div>
              </ScrollArea>
              {applyRoute.data ? (
                <Alert className="mt-3" variant="success">
                  <AlertDescription>
                    <p className="font-semibold">{format(ti.workflowCreated, { workflowRunId: applyRoute.data.workflow_run.id })}</p>
                    <p>{applyRoute.data.module_selection_note}</p>
                    {applyRoute.data.module_selection_override?.dropped_modules.length ? <p>{ti.droppedModules} {applyRoute.data.module_selection_override.dropped_modules.join(', ')}</p> : null}
                    {applyRoute.data.parameter_lineage?.length ? (
                      <div className="mt-2">
                        <p className="font-semibold">{ti.parameterLineage}</p>
                        <ul className="grid gap-1">
                          {applyRoute.data.parameter_lineage.slice(0, 4).map((item, index) => (
                            <li key={`${item.residue ?? 'constraint'}-${item.region ?? index}`}>{item.residue ?? item.region}: {(item.parameter_targets ?? []).join(', ')}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {applyRoute.data.next_actions?.length ? <ol className="mt-2 grid gap-1">{applyRoute.data.next_actions.map((action) => <li key={action}>{action}</li>)}</ol> : null}
                    {projectId ? <Button className="mt-2" variant="outline" size="sm" render={<Link to={`/workflow?project=${encodeURIComponent(projectId)}`} />}>{ti.openWorkflowDag}</Button> : null}
                  </AlertDescription>
                </Alert>
              ) : null}
              {applyRoute.isError ? <Alert className="mt-3" variant="destructive"><AlertDescription>{ti.workflowCreateFailed}</AlertDescription></Alert> : null}
            </FramePanel>
          </Frame>

          <Frame className="min-h-[20rem] lg:min-h-0" spacing="sm">
            <FramePanel className="flex min-h-0 flex-col">
              <FrameHeader className="flex-row flex-wrap items-center justify-between">
                <FrameTitle>{ti.dossierExportTitle}</FrameTitle>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={!runId || mutationPending} onClick={() => exportDossier.mutate('json')}>{ti.exportJson}</Button>
                  <Button type="button" variant="outline" size="sm" disabled={!runId || mutationPending} onClick={() => exportDossier.mutate('markdown')}>{ti.exportMarkdown}</Button>
                  <Button type="button" variant="outline" size="icon-sm" aria-label={ti.downloadExportTitle} disabled={!exportDossier.data || mutationPending} onClick={downloadPreview}>
                    <DownloadSimpleIcon aria-hidden="true" />
                  </Button>
                </div>
              </FrameHeader>
              <ScrollArea className="mt-3 min-h-0 flex-1">
                <pre className="min-w-max whitespace-pre-wrap p-1 text-xs text-muted-foreground">{exportPreview || ti.exportPreviewEmpty}</pre>
              </ScrollArea>
            </FramePanel>
          </Frame>
        </div>
      </section>
    </div>
  )
}
