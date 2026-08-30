import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowSquareOutIcon,
  ChatCircleIcon,
  FileMagnifyingGlassIcon,
  MagnifyingGlassIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import type {
  ResearchWorkspaceStructure,
} from '../../lib/api/generated/types.gen'
import {
  getResearchWorkspace,
  workspaceText,
} from '../../lib/api/researchWorkspace'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Filters, type Filter, type FilterFieldConfig } from '../../components/reui/filters'
import {
  Frame,
  FrameDescription,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '../../components/reui/frame'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import { structureSourceFromUrl } from '../pdb-viewer/types'
import { GenerateSimilarResearchPanel } from './GenerateSimilarResearchPanel'
import { KnowledgePanel } from './KnowledgePanel'
import { LiteraturePanel } from './LiteraturePanel'
import { ProjectReviewPanel } from './ProjectReviewPanel'
import { ResearchGapResolutionButton } from './ResearchGapResolutionButton'
import { ReviewMarkdown } from './ReviewMarkdown'
import { DryLabDecisionTree } from './DryLabDecisionTree'
import {
  DatasetDataGrid,
  ResearchTargetDataGrid,
  type ResearchGridLabels,
} from './ResearchDataGrids'
import { TargetIntelligencePanel } from './TargetIntelligencePanel'
import type { ResearchTab } from './researchUi'

function OperationBlock({ title, children }: { title: string; children: React.ReactNode }) {
  const [openItems, setOpenItems] = useState<string[]>([])
  const open = openItems.includes('operation')
  return (
    <Frame dense data-tour-id="research-operations">
      <FramePanel className="p-0">
        <Accordion value={openItems} onValueChange={setOpenItems}>
          <AccordionItem value="operation" className="border-0">
            <AccordionTrigger className="px-4 py-3 text-sm">{title}</AccordionTrigger>
            <AccordionContent className="border-t p-4">
              {open ? children : null}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </FramePanel>
    </Frame>
  )
}

function SectionHeading({ title }: { title: string }) {
  return <h3 className="text-base font-semibold text-text-primary">{title}</h3>
}

function AskCopilotButton({ entityId, entityType, label }: { entityId: string; entityType: string; label: string }) {
  const { language, t, format } = useI18n()
  const setDraft = useAppStore((state) => state.setCopilotDraft)
  const setOpen = useAppStore((state) => state.setCopilotOpen)
  const setSelected = useAppStore((state) => state.setCopilotSelectedEntityIds)
  const ask = () => {
    setSelected([entityId])
    setDraft(language === 'zh'
      ? `请仅依据 Research workspace 分析所选${entityType}“${label}”（实体 ID：${entityId}），给出实体级引用、证据等级、审核状态和信息缺口。`
      : `Analyze the selected ${entityType} "${label}" (entity ID: ${entityId}) using only Research workspace evidence. Include entity-level citations, evidence grade, review status, and gaps.`)
    setOpen(true)
  }
  return (
    <Button
      type="button"
      variant="outline"
      size="xs"
      onClick={ask}
      aria-label={format(t.research.workspace.askCopilotAbout, { label })}
    >
      <ChatCircleIcon aria-hidden="true" />
      Copilot
    </Button>
  )
}

function StructureWorkspace({ structures, projectId }: { structures: ResearchWorkspaceStructure[]; projectId: string }) {
  const { language, t } = useI18n()
  const w = t.research.workspace
  if (!structures.length) {
    return (
      <Alert>
        <AlertDescription>{w.structuresEmpty}</AlertDescription>
      </Alert>
    )
  }
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {structures.map((item) => (
        <Frame key={item.artifact_id} dense>
          <FramePanel className="p-0">
          {item.download_url ? (
            <StructureViewerLazy
              source={structureSourceFromUrl(item.download_url, {
                projectId,
                artifactId: item.artifact_id,
                pdbId: item.pdb_id,
                proteinName: workspaceText(item.name, language),
                chains: Array.isArray(item.lineage?.chains)
                  ? item.lineage.chains.filter((chain): chain is string => typeof chain === 'string')
                  : undefined,
              })}
              height={280}
              showMetadata
            />
          ) : null}
          <div className="p-4">
          <div className="flex items-start justify-between gap-3">
            <span className="font-mono text-xs text-accent">{item.pdb_id ? `PDB ${item.pdb_id}` : item.artifact_id}</span>
            <Badge variant={item.status === 'available' ? 'success-light' : 'secondary'} size="xs">
              {item.status === 'available' ? w.statusAvailable : item.status.replaceAll('_', ' ')}
            </Badge>
          </div>
          <h3 className="mt-2 text-sm font-semibold text-text-primary">{workspaceText(item.name, language)}</h3>
          <p className="mt-1 text-xs text-text-secondary">{workspaceText(item.role, language) || workspaceText(item.method, language) || '—'}</p>
          <p className="mt-3 text-xs text-text-muted">
            {workspaceText(item.method, language) || '—'} · {item.resolution ? `${item.resolution} Å` : w.resolutionUnavailable}
          </p>
          {item.reference_id ? <p className="mt-2 text-xs text-text-muted">{item.reference_id}</p> : null}
          <div className="mt-3 flex items-center gap-2">{item.rcsb_url ? <a className="inline-flex items-center gap-1 text-xs text-accent hover:underline" href={item.rcsb_url} target="_blank" rel="noopener noreferrer"><ArrowSquareOutIcon aria-hidden="true" />RCSB</a> : null}<AskCopilotButton entityId={item.artifact_id} entityType="structure" label={workspaceText(item.name, language)} /></div>
          </div>
          </FramePanel>
        </Frame>
      ))}
    </section>
  )
}

function ReferenceUrl({ url, label }: { url: string; label: string }) {
  return <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-accent hover:underline"><FileMagnifyingGlassIcon aria-hidden="true" />{label}</a>
}

export function ResearchWorkspacePanel({ view }: { view: ResearchTab }) {
  const { activeProject, projectId } = useProjectContext()
  const { language, t, format } = useI18n()
  const w = t.research.workspace
  const [search, setSearch] = useState('')
  const [assertionFilters, setAssertionFilters] = useState<Filter<string>[]>([])
  const readOnly = useAppStore((state) => state.appMode === 'demo')
  const workspaceQuery = useQuery({
    queryKey: ['research-workspace', projectId],
    queryFn: () => getResearchWorkspace(projectId),
    enabled: Boolean(projectId),
  })
  const workspace = workspaceQuery.data
  const assertionLabel = (value: string) => ({
    established_fact: w.assertionEstablishedFact,
    evidence_based_inference: w.assertionEvidenceInference,
    hypothesis: w.assertionHypothesis,
    counterevidence: w.assertionCounterevidence,
  }[value] ?? value.replaceAll('_', ' '))
  const statusLabel = (value: string) => ({
    pending_review: w.statusPendingReview,
    accepted: w.statusAccepted,
    rejected: w.statusRejected,
    confirmed: w.statusConfirmed,
    available: w.statusAvailable,
  }[value] ?? value.replaceAll('_', ' '))
  const assertionValues = Array.from(new Set(workspace?.graph_edges.map((edge) => edge.assertion) ?? []))
  const assertionFields: FilterFieldConfig<string>[] = [{
    key: 'assertion',
    label: w.assertionFilterLabel,
    type: 'multiselect',
    searchable: false,
    operators: [{
      value: 'is_any_of',
      label: w.filterIsAnyOf,
      supportsMultiple: true,
    }],
    defaultOperator: 'is_any_of',
    options: assertionValues.map((value) => ({ value, label: assertionLabel(value) })),
  }]

  if (!activeProject || !projectId) return null
  if (workspaceQuery.isLoading) return (
    <Frame>
      <FramePanel role="status" aria-live="polite" className="grid gap-3">
        <Skeleton className="h-5 w-52" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-28 w-full" />
        <span className="sr-only">{w.loading}</span>
      </FramePanel>
    </Frame>
  )
  if (workspaceQuery.isError) return (
    <Alert variant="destructive" role="status" aria-live="polite">
      <WarningCircleIcon aria-hidden="true" />
      <AlertTitle>{w.loadFailed}</AlertTitle>
      <AlertDescription>
        <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => workspaceQuery.refetch()}>
          {w.retry}
        </Button>
      </AlertDescription>
    </Alert>
  )
  if (!workspace) return (
    <Alert role="status">
      <AlertDescription>{w.empty}</AlertDescription>
    </Alert>
  )

  const packageInfo = workspace.project.package ?? {}
  const packageVersion = typeof packageInfo.version === 'string' ? packageInfo.version : ''
  const packageDate = typeof packageInfo.as_of === 'string' ? packageInfo.as_of : ''
  const selectedAssertions = assertionFilters
    .filter((filter) => filter.field === 'assertion' && filter.operator === 'is_any_of')
    .flatMap((filter) => filter.values)
  const edges = workspace.graph_edges.filter(
    (edge) => !selectedAssertions.length || selectedAssertions.includes(edge.assertion),
  ).filter((edge) => {
    const term = search.trim().toLowerCase()
    if (!term) return true
    return [edge.source, edge.target, edge.predicate, workspaceText(edge.source_label, language), workspaceText(edge.target_label, language), workspaceText(edge.summary, language), workspaceText(edge.context, language)].join(' ').toLowerCase().includes(term)
  })
  return (
    <div className="grid gap-4">
      <Frame>
        <FramePanel>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-accent">{workspace.project.source_project_key || workspace.project.project_type}</p>
            <h2 className="mt-1 text-lg font-semibold">{workspaceText(workspace.project.name, language)}</h2>
            <p className="mt-1 max-w-3xl text-sm text-text-secondary">{workspaceText(workspace.project.summary, language)}</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
            {packageVersion ? <Badge variant="outline">{format(w.packageVersion, { version: packageVersion })}</Badge> : null}
            {packageDate ? <Badge variant="outline">{format(w.evidenceAsOf, { date: packageDate })}</Badge> : null}
            <Badge variant="secondary">{format(w.referencesCount, { count: workspace.references.length })}</Badge>
            <Badge variant="secondary">{format(w.targetsCount, { count: workspace.research_targets.length })}</Badge>
            <Badge variant="secondary">{format(w.structuresCount, { count: workspace.structures.length })}</Badge>
          </div>
        </div>
        </FramePanel>
      </Frame>

      {view === 'evidence' ? (
        <>
          {workspace.review_document ? (
            <Frame>
              <FramePanel>
              <div className="flex items-start justify-between gap-3"><SectionHeading title={w.reviewTitle} /><AskCopilotButton entityId={workspace.review_document.id} entityType="review" label={workspaceText(workspace.review_document.title, language)} /></div>
              <div className="mt-4"><ReviewMarkdown>{workspaceText(workspace.review_document.content, language)}</ReviewMarkdown></div>
              </FramePanel>
            </Frame>
          ) : <Alert><AlertDescription>{w.reviewEmpty}</AlertDescription></Alert>}
          <ProjectReviewPanel workspace={workspace} showDocument={false} readOnly={readOnly} />
          <Frame>
            <FramePanel className="grid gap-4">
              <FrameHeader className="px-0 py-0">
                <FrameTitle>{w.evidenceTitle}</FrameTitle>
                <FrameDescription>{w.evidenceDescription}</FrameDescription>
              </FrameHeader>
              <div className="flex flex-wrap gap-2">
                <label className="relative min-w-64 flex-1">
                  <MagnifyingGlassIcon aria-hidden="true" className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" />
                  <Input
                    aria-label={w.evidenceSearch}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={w.evidenceSearch}
                    className="pl-8"
                  />
                </label>
                <div data-testid="research-assertion-filters" data-slot="filters">
                  <Filters
                    filters={assertionFilters}
                    fields={assertionFields}
                    onChange={setAssertionFilters}
                    allowMultiple={false}
                    size="sm"
                    i18n={{
                      addFilter: w.addAssertionFilter,
                      searchFields: w.searchFilterFields,
                    }}
                  />
                </div>
              </div>
            {edges.length ? edges.map((edge) => <article key={edge.id} className="border bg-muted/30 p-4">
              <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase"><span className="font-mono text-xs text-primary">{edge.id}</span><Badge variant="outline" size="xs">{format(w.grade, { grade: edge.evidence_grade })}</Badge><Badge variant="info-light" size="xs">{assertionLabel(edge.assertion)}</Badge><Badge variant="secondary" size="xs">{statusLabel(edge.review_status || '')}</Badge><AskCopilotButton entityId={edge.id} entityType="evidence relation" label={workspaceText(edge.summary, language) || edge.id} /></div>
              <p className="mt-2 font-medium"><strong>{workspaceText(edge.source_label, language)}</strong> <span className="text-accent">—{edge.predicate}→</span> <strong>{workspaceText(edge.target_label, language)}</strong></p>
              <p className="mt-2 text-sm text-text-secondary">{workspaceText(edge.summary, language)}</p>
              {workspaceText(edge.context, language) ? <p className="mt-2 text-xs text-text-muted">{workspaceText(edge.context, language)}</p> : null}
              <div className="mt-3 flex flex-wrap gap-2">{edge.source_urls?.map((url, index) => <ReferenceUrl key={url} url={url} label={edge.reference_ids?.[index] || edge.reference_ids?.[0] || url} />)}</div>
            </article>) : <Alert><AlertDescription>{w.evidenceEmpty}</AlertDescription></Alert>}
            </FramePanel>
          </Frame>
          <OperationBlock title={w.evidenceOperations}>
            <GenerateSimilarResearchPanel
              defaultTopic={
                workspace.project.name.en
                || workspace.project.name.default
                || workspaceText(workspace.project.name, language)
                || activeProject.name
              }
            />
          </OperationBlock>
        </>
      ) : null}

      {view === 'references' ? (
        <>
          <Frame>
            <FramePanel className="grid gap-3">
              <FrameHeader className="px-0 py-0">
                <FrameTitle>{w.referencesTitle}</FrameTitle>
                <FrameDescription>{w.referencesDescription}</FrameDescription>
              </FrameHeader>
            {workspace.references.length ? workspace.references.map((reference) => {
              const links = [
                reference.url ? { url: reference.url, label: reference.ref_id } : null,
                reference.doi ? { url: `https://doi.org/${reference.doi}`, label: `DOI ${reference.doi}` } : null,
                reference.pmid ? { url: `https://pubmed.ncbi.nlm.nih.gov/${reference.pmid}/`, label: `PMID ${reference.pmid}` } : null,
              ].filter((link): link is { url: string; label: string } => Boolean(link))
                .filter((link, index, values) => values.findIndex((candidate) => candidate.url === link.url) === index)
              return <article key={reference.document_id} className="border bg-muted/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-xs text-accent">{reference.ref_id} · {reference.verification_status || reference.status}</span><div className="flex items-center gap-2"><span className="text-xs text-text-muted">{[reference.year, reference.journal].filter(Boolean).join(' · ')}</span><AskCopilotButton entityId={reference.document_id} entityType="reference" label={workspaceText(reference.title, language)} /></div></div>
                <h3 className="mt-2 font-semibold">{workspaceText(reference.title, language)}</h3>{reference.authors ? <p className="mt-1 text-xs text-text-secondary">{reference.authors}</p> : null}
                {links.length ? <div className="mt-3 flex flex-wrap gap-3">{links.map((link) => <ReferenceUrl key={link.url} url={link.url} label={link.label} />)}</div> : null}
              </article>
            }) : <Alert><AlertDescription>{w.referencesEmpty}</AlertDescription></Alert>}
            </FramePanel>
          </Frame>
          <OperationBlock title={w.referenceOperations}><LiteraturePanel /></OperationBlock>
        </>
      ) : null}

      {view === 'structures' ? <><Frame variant="ghost"><FramePanel className="grid gap-4"><FrameHeader className="px-0 py-0"><FrameTitle>{w.structuresTitle}</FrameTitle><FrameDescription>{w.structuresDescription}</FrameDescription></FrameHeader><StructureWorkspace structures={workspace.structures} projectId={projectId} /></FramePanel></Frame><OperationBlock title={w.structureOperations}><TargetIntelligencePanel /></OperationBlock></> : null}

      {view === 'data' ? (
        <section className="grid min-h-0 gap-4">
          <div>
            <SectionHeading title={w.dataTitle} />
            <p className="mt-1 text-sm text-muted-foreground">{w.dataDescription}</p>
          </div>
          <ResearchTargetDataGrid
            targets={workspace.research_targets}
            labels={w as ResearchGridLabels}
            language={language}
            renderAskCopilot={(entityId, entityType, label) => (
              <AskCopilotButton entityId={entityId} entityType={entityType} label={label} />
            )}
            renderTargetAction={(target) => (
              <ResearchGapResolutionButton
                projectId={projectId}
                researchTargetId={target.id}
                properties={target.properties ?? {}}
              />
            )}
          />
          {workspace.datasets.length ? workspace.datasets.map((dataset) => (
            <DatasetDataGrid
              key={dataset.id}
              dataset={dataset}
              labels={w as ResearchGridLabels}
              language={language}
              renderAskCopilot={(entityId, entityType, label) => (
                <AskCopilotButton entityId={entityId} entityType={entityType} label={label} />
              )}
            />
          )) : <Alert><AlertDescription>{w.dataEmpty}</AlertDescription></Alert>}
        </section>
      ) : null}

      {view === 'methods' ? (
        <>
          <DryLabDecisionTree projectId={projectId} />
          <Frame>
            <FramePanel className="grid gap-4">
              <FrameHeader className="px-0 py-0"><FrameTitle>{w.methodsTitle}</FrameTitle><FrameDescription>{w.methodsDescription}</FrameDescription></FrameHeader>
              {/* Methods entries are long-form documents, so each one collapses; the
                  first stays open so the tab still shows content on arrival. */}
              {workspace.methods.length ? (
                <Accordion defaultValue={[workspace.methods[0].id]}>
                  {workspace.methods.map((method) => (
                    <AccordionItem key={method.id} value={method.id}>
                      <AccordionTrigger className="text-sm">{workspaceText(method.title, language)}</AccordionTrigger>
                      <AccordionContent className="border-t p-4">
                        <div className="mb-3"><AskCopilotButton entityId={method.id} entityType="method" label={workspaceText(method.title, language)} /></div>
                        <ReviewMarkdown>{workspaceText(method.content, language)}</ReviewMarkdown>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              ) : <Alert><AlertDescription>{w.methodsEmpty}</AlertDescription></Alert>}
            </FramePanel>
          </Frame>
          <OperationBlock title={w.methodsOperations}><KnowledgePanel /></OperationBlock>
        </>
      ) : null}
    </div>
  )
}
