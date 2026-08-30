import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowSquareOutIcon,
  CheckCircleIcon,
  DatabaseIcon,
  MagnifyingGlassIcon,
  ShieldCheckIcon,
  SpinnerGapIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import {
  createResearchGeneration,
  importResearchGeneration,
  waitForResearchGeneration,
  type ResearchGeneration,
} from '../../lib/api/copilotResearch'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function array(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(record) : []
}

function draftText(value: unknown, language: 'en' | 'zh'): string {
  const localized = record(value)
  return typeof value === 'string'
    ? value
    : String(localized[language] || localized.default || localized.en || localized.zh || '')
}

export function GenerateSimilarResearchPanel({ defaultTopic }: { defaultTopic: string }) {
  const { t, format, language } = useI18n()
  const g = t.research.similarGeneration
  const { projectId, setProjectId } = useProjectContext()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [topic, setTopic] = useState(defaultTopic)
  const [strata, setStrata] = useState('')
  const [candidateCount, setCandidateCount] = useState(10)
  const [deadline, setDeadline] = useState('')
  const [generation, setGeneration] = useState<ResearchGeneration | null>(null)
  const [openDetails, setOpenDetails] = useState<string[]>(['references'])
  const previousDefaultTopic = useRef(defaultTopic)

  useEffect(() => {
    setTopic((current) => current === previousDefaultTopic.current ? defaultTopic : current)
    previousDefaultTopic.current = defaultTopic
  }, [defaultTopic])

  const importDraft = useMutation({
    mutationFn: async () => {
      if (!generation?.checksum) throw new Error(g.checksumMissing)
      return importResearchGeneration(generation.id, generation.checksum)
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      await queryClient.invalidateQueries({ queryKey: ['project-library'] })
      await queryClient.refetchQueries({ queryKey: ['projects'] })
      setProjectId(result.project_id)
      navigate(`/research?project=${encodeURIComponent(result.project_id)}&tab=references`)
    },
  })
  const generate = useMutation({
    mutationFn: async () => {
      const accepted = await createResearchGeneration(projectId, {
        topic: topic.trim(), strata: strata.trim(), candidate_count: candidateCount, use_external_evidence: true,
        evidence_cutoff: deadline || undefined, language,
      })
      return waitForResearchGeneration(accepted.generation_id)
    },
    onMutate: () => {
      setGeneration(null)
      setOpenDetails(['references'])
      importDraft.reset()
    },
    onSuccess: setGeneration,
  })

  const counts = generation?.draft && typeof generation.draft.counts === 'object'
    ? generation.draft.counts as Record<string, number>
    : {}
  const issues = generation?.validation?.issues ?? []
  const draft = record(generation?.draft)
  const references = array(draft.references)
  const graphEdges = array(draft.graph_edges)
  const researchTargets = array(draft.research_targets)
  const reviewSections = array(draft.review_sections)
  const provenance = record(draft.provenance)
  const referenceCounts = record(provenance.reference_counts)
  const copiedReferences = Number(referenceCounts.copied_from_source ?? references.filter((item) => record(item.metadata).origin === 'source_project').length)
  const discoveredReferences = Number(referenceCounts.newly_discovered ?? references.filter((item) => record(item.metadata).origin === 'external_discovery').length)
  const valid = generation?.validation?.valid === true
  const stages = Object.values(g.stages)

  return (
    <div className="grid gap-4">
      <Frame spacing="sm">
        <FramePanel>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-1"><Label htmlFor="generation-topic">{g.topicLabel}</Label><Input id="generation-topic" value={topic} onChange={(event) => setTopic(event.target.value)} /></div>
            <div className="grid gap-1"><Label htmlFor="generation-strata">{g.strataLabel}</Label><Input id="generation-strata" value={strata} onChange={(event) => setStrata(event.target.value)} /></div>
            <div className="grid gap-1"><Label htmlFor="generation-count">{g.candidateCountLabel}</Label><Input id="generation-count" type="number" min={1} max={100} value={candidateCount} onChange={(event) => setCandidateCount(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></div>
            <div className="grid gap-1"><Label htmlFor="generation-deadline">{g.evidenceCutoffLabel}</Label><Input id="generation-deadline" type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} /></div>
          </div>
          <Button type="button" className="mt-3" disabled={!projectId || !topic.trim() || generate.isPending || importDraft.isPending} onClick={() => generate.mutate()}>
            {generate.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <MagnifyingGlassIcon aria-hidden="true" />}
            {generate.isPending ? g.pending : g.generate}
          </Button>
          {(generate.isPending || generation) ? (
            <div className="mt-3 flex flex-wrap gap-2" aria-label={g.progressLabel}>
              {stages.map((stage, index) => {
                const complete = generation?.status === 'ready' || generation?.status === 'imported'
                const failed = generation?.status === 'failed'
                return (
                  <Badge key={stage} variant={complete ? 'success-light' : failed ? 'destructive-light' : 'info-light'} size="xs">
                    {complete ? <CheckCircleIcon aria-hidden="true" /> : <SpinnerGapIcon className={generate.isPending && index === 0 ? 'animate-spin' : ''} aria-hidden="true" />}
                    {stage}
                  </Badge>
                )
              })}
            </div>
          ) : null}
          {generate.isError ? <Alert className="mt-3" variant="destructive" role="alert"><WarningIcon aria-hidden="true" /><AlertDescription>{generate.error instanceof Error ? generate.error.message : String(generate.error)}</AlertDescription></Alert> : null}
        </FramePanel>
      </Frame>

      {generation?.status === 'ready' ? (
        <Frame data-testid="research-generation-preview" spacing="sm">
          <FramePanel>
            <Alert variant={valid ? 'success' : 'warning'}>
              {valid ? <ShieldCheckIcon aria-hidden="true" /> : <WarningIcon aria-hidden="true" />}
              <AlertTitle>{valid ? g.readyTitle : g.incompleteTitle}</AlertTitle>
            </Alert>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(counts).map(([key, value]) => <Badge key={key} variant="secondary" size="xs">{key}: {value}</Badge>)}
              <Badge variant="outline" size="xs">{format(g.inheritedCount, { count: copiedReferences })}</Badge>
              <Badge variant="info-light" size="xs">{format(g.discoveredCount, { count: discoveredReferences })}</Badge>
              <Badge variant="warning-light" size="xs">{g.metadataOnly}</Badge>
            </div>
            <p className="mt-3 font-mono text-[10px] text-muted-foreground">SHA-256 {generation.checksum}</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              <Frame spacing="xs"><FramePanel><strong className="text-xs">{g.recordsToCreate}</strong><pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-[10px] text-muted-foreground">{JSON.stringify(generation.validation.records_to_create ?? counts, null, 2)}</pre></FramePanel></Frame>
              <Frame spacing="xs"><FramePanel><strong className="text-xs">{g.missingCategories}</strong><p className="mt-1 text-muted-foreground">{generation.validation.missing_categories?.length ? generation.validation.missing_categories.join(', ') : g.none}</p></FramePanel></Frame>
            </div>
            {issues.length ? <Alert className="mt-3" variant="warning"><WarningIcon aria-hidden="true" /><AlertTitle>{g.validationNotes}</AlertTitle><AlertDescription><ul className="list-disc pl-4">{issues.map((issue, index) => <li key={index}>{String(issue.kind ?? 'issue')}: {String(issue.detail ?? '')}</li>)}</ul></AlertDescription></Alert> : null}

            <Accordion className="mt-3" value={openDetails} onValueChange={setOpenDetails}>
              <AccordionItem value="references">
                <AccordionTrigger>{format(g.referenceDetails, { count: references.length })}</AccordionTrigger>
                <AccordionContent>
                  {openDetails.includes('references') ? (
                    <div className="grid gap-2">
                      {references.map((reference, index) => {
                        const metadata = record(reference.metadata)
                        const doi = String(reference.doi || '')
                        const pmid = String(reference.pmid || '')
                        const url = doi ? `https://doi.org/${doi}` : pmid ? `https://pubmed.ncbi.nlm.nih.gov/${pmid}/` : String(reference.url || '')
                        const origin = metadata.origin === 'external_discovery' ? g.discoveredOrigin : g.inheritedOrigin
                        const scope = metadata.retrieval_scope === 'full_text' ? g.fullText : metadata.retrieval_scope === 'abstract_or_metadata' ? g.abstractMetadata : g.metadataScope
                        return (
                          <Frame key={String(reference.document_id || reference.ref_id || index)} spacing="xs">
                            <FramePanel>
                              <div className="flex flex-wrap gap-2">
                                <Badge variant="secondary" size="xs">{String(reference.ref_id || '')}</Badge>
                                <Badge variant="info-light" size="xs">{origin}</Badge>
                                <Badge variant="outline" size="xs">{scope}</Badge>
                                <Badge variant="outline" size="xs">{String(reference.verification_status || '')}</Badge>
                              </div>
                              <h4 className="mt-1 font-semibold">{draftText(reference.title, language)}</h4>
                              {reference.authors ? <p className="mt-1 text-muted-foreground">{String(reference.authors)}</p> : null}
                              <p className="mt-1 text-muted-foreground">{[reference.year, reference.journal].filter(Boolean).map(String).join(' · ')}</p>
                              {url ? <a className="mt-2 inline-flex items-center gap-1 text-primary hover:underline" href={url} target="_blank" rel="noopener noreferrer"><ArrowSquareOutIcon aria-hidden="true" />{doi ? `DOI ${doi}` : pmid ? `PMID ${pmid}` : String(reference.ref_id || url)}</a> : null}
                            </FramePanel>
                          </Frame>
                        )
                      })}
                      {!references.length ? <p className="text-muted-foreground">{g.noReferences}</p> : null}
                    </div>
                  ) : null}
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="records">
                <AccordionTrigger>{g.recordDetails}</AccordionTrigger>
                <AccordionContent>
                  {openDetails.includes('records') ? (
                    <div className="grid gap-3 md:grid-cols-3">
                      <div><strong>{format(g.reviewSections, { count: reviewSections.length })}</strong>{reviewSections.map((section, index) => <p key={index} className="mt-1 text-muted-foreground">{String(section.track || '')}: {array(section.items).length}</p>)}</div>
                      <div><strong>{format(g.researchTargets, { count: researchTargets.length })}</strong>{researchTargets.map((target, index) => <p key={index} className="mt-1 text-muted-foreground">{String(target.candidate_key || '')} · {draftText(target.name, language)}</p>)}</div>
                      <div><strong>{format(g.evidenceRelations, { count: graphEdges.length })}</strong>{graphEdges.map((edge, index) => <p key={index} className="mt-1 text-muted-foreground">{draftText(edge.summary, language) || String(edge.id || '')}</p>)}</div>
                    </div>
                  ) : null}
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            <Button type="button" className="mt-3" disabled={!valid || importDraft.isPending} title={!valid ? g.blockedHint : undefined} onClick={() => importDraft.mutate()}>
              {importDraft.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <DatabaseIcon aria-hidden="true" />}
              {g.confirm}
            </Button>
          </FramePanel>
        </Frame>
      ) : null}
      {generation?.status === 'failed' ? <Alert variant="destructive" role="alert"><WarningIcon aria-hidden="true" /><AlertTitle>{g.validationFailed}</AlertTitle><AlertDescription><p>{generation.error}</p>{issues.length ? <ul className="mt-2 list-disc pl-4">{issues.map((issue, index) => <li key={index}>{String(issue.kind)}: {String(issue.detail ?? '')}</li>)}</ul> : null}</AlertDescription></Alert> : null}
      {importDraft.isSuccess ? <Alert variant="success" role="status"><CheckCircleIcon aria-hidden="true" /><AlertDescription>{g.importSuccess}</AlertDescription></Alert> : null}
      {importDraft.isError ? <Alert variant="destructive" role="alert"><AlertDescription>{importDraft.error instanceof Error ? importDraft.error.message : String(importDraft.error)}</AlertDescription></Alert> : null}
    </div>
  )
}
