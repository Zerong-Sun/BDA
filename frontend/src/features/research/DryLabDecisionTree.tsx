import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowDownIcon, FileTextIcon, GitBranchIcon } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FrameDescription, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { StatusPill } from '../../components/ui/StatusPill'
import type { StatusTone } from '../../components/ui/statusTone'
import { listAllTimeline } from '../../lib/api/timeline'
import { groupByPhase, provenanceRefs, type TimelineEntry } from '../../lib/schemas/timeline'
import { useI18n } from '../../lib/i18n'
import { ReviewMarkdown } from './ReviewMarkdown'

function outcomeTone(outcome: string): StatusTone {
  if (outcome === 'supported') return 'green'
  if (outcome === 'refuted') return 'red'
  if (outcome === 'inconclusive') return 'amber'
  return 'neutral'
}

function DecisionNode({
  entry,
  entriesById,
  isLast,
}: {
  entry: TimelineEntry
  entriesById: ReadonlyMap<string, TimelineEntry>
  isLast: boolean
}) {
  const { t } = useI18n()
  const tl = t.timeline
  const refs = provenanceRefs(entry)
  const type = tl.type[entry.entry_type as keyof typeof tl.type] ?? entry.entry_type
  const outcome = tl.outcome[entry.outcome as keyof typeof tl.outcome] ?? entry.outcome
  const superseded = entry.supersedes_id ? entriesById.get(entry.supersedes_id) : undefined
  const cause = entry.caused_by_id ? entriesById.get(entry.caused_by_id) : undefined

  return (
    <li className="relative pl-7">
      <span
        aria-hidden="true"
        className="absolute left-[7px] top-5 size-2.5 rounded-full border-2 border-primary bg-background"
      />
      {!isLast ? <span aria-hidden="true" className="absolute bottom-[-1rem] left-3 top-7 border-l border-border" /> : null}
      <article className="rounded-md border border-border bg-background p-3 shadow-xs">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" size="xs">{type}</Badge>
          <StatusPill label={outcome} tone={outcomeTone(entry.outcome)} />
          <time className="ml-auto font-mono text-[10px] text-muted-foreground" dateTime={entry.occurred_at}>
            {entry.occurred_at.slice(0, 10)}
          </time>
        </div>
        <h4 className="mt-2 text-sm font-semibold text-foreground">{entry.title}</h4>
        {entry.summary ? <p className="mt-1 text-xs text-muted-foreground">{entry.summary}</p> : null}
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.tags.map((tag, index) => <Badge key={`${tag}:${index}`} variant="secondary" size="xs">#{tag}</Badge>)}
        </div>
        {entry.supersedes_id || entry.caused_by_id ? (
          <dl className="mt-2 grid gap-1 rounded-md border border-border bg-muted/30 px-2 py-1.5 text-[11px]">
            {entry.supersedes_id ? (
              <div className="flex min-w-0 gap-1">
                <dt className="shrink-0 text-muted-foreground">{tl.supersedes}:</dt>
                <dd className="truncate font-medium text-foreground" title={superseded?.title ?? entry.supersedes_id}>
                  {superseded?.title ?? entry.supersedes_id}
                </dd>
              </div>
            ) : null}
            {entry.caused_by_id ? (
              <div className="flex min-w-0 gap-1">
                <dt className="shrink-0 text-muted-foreground">{tl.causedBy}:</dt>
                <dd className="truncate font-medium text-foreground" title={cause?.title ?? entry.caused_by_id}>
                  {cause?.title ?? entry.caused_by_id}
                </dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        {entry.body ? (
          <Accordion className="mt-3 border-t border-border" defaultValue={[]}>
            <AccordionItem value={entry.id} className="border-0">
              <AccordionTrigger className="text-primary">
                <span className="flex items-center gap-1"><FileTextIcon aria-hidden="true" />{tl.decisionDocument}</span>
              </AccordionTrigger>
              <AccordionContent className="pt-2 text-sm"><ReviewMarkdown>{entry.body}</ReviewMarkdown></AccordionContent>
            </AccordionItem>
          </Accordion>
        ) : null}
        {refs.length || entry.code_refs.length ? (
          <div className="mt-3 flex flex-wrap gap-1 border-t border-border pt-2 text-[10px] text-muted-foreground">
            {refs.map((ref, index) => (
              <span key={`${ref.kind}:${ref.value}:${index}`} className="rounded bg-muted px-1.5 py-0.5 font-mono">
                {ref.kind}: {ref.value}
              </span>
            ))}
            {entry.code_refs.map((ref, index) => (
              <span key={`${ref.path}:${ref.role}:${index}`} className="rounded bg-muted px-1.5 py-0.5 font-mono">
                {ref.path}{ref.role ? ` · ${ref.role}` : ''}
              </span>
            ))}
          </div>
        ) : null}
      </article>
    </li>
  )
}

export function DryLabDecisionTree({ projectId }: { projectId: string }) {
  const { t, format } = useI18n()
  const copy = t.research.workspace
  const tl = t.timeline
  const query = useQuery({
    queryKey: ['project-timeline', projectId],
    queryFn: () => listAllTimeline(projectId),
    staleTime: 60_000,
  })
  const branches = useMemo(() => groupByPhase(query.data ?? []), [query.data])
  const entriesById = useMemo(
    () => new Map((query.data ?? []).map((entry) => [entry.id, entry])),
    [query.data],
  )

  return (
    <Frame data-tour-id="dry-lab-decision-tree">
      <FramePanel className="grid gap-4">
        <FrameHeader className="px-0 py-0">
          <div className="flex items-center gap-2">
            <GitBranchIcon aria-hidden="true" className="size-5 text-primary" />
            <FrameTitle>{copy.decisionTreeTitle}</FrameTitle>
          </div>
          <FrameDescription>{copy.decisionTreeDescription}</FrameDescription>
        </FrameHeader>
        {query.isLoading ? <p className="text-sm text-muted-foreground" role="status">{tl.loading}</p> : null}
        {query.isError ? (
          <Alert variant="destructive" role="alert">
            <AlertDescription>
              <p>{tl.loadFailed}</p>
              <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => query.refetch()}>
                {t.common.retry}
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
        {!query.isLoading && !query.isError && !branches.length ? (
          <Alert><AlertDescription>{copy.decisionTreeEmpty}</AlertDescription></Alert>
        ) : null}
        {branches.length ? (
          <div className="overflow-x-auto pb-2">
            <div
              className="grid min-w-max items-start gap-4"
              style={{ gridTemplateColumns: `repeat(${branches.length}, minmax(19rem, 23rem))` }}
            >
              {branches.map((branch, branchIndex) => (
                <section key={branch.phase || `branch-${branchIndex}`} className="rounded-lg border border-border bg-muted/20 p-3">
                  <header className="mb-4 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
                    <GitBranchIcon aria-hidden="true" className="text-primary" />
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold text-foreground">{branch.phase || tl.noPhase}</h3>
                      <p className="text-[10px] text-muted-foreground">
                        {format(copy.decisionTreeBranchCount, { count: branch.entries.length })}
                      </p>
                    </div>
                  </header>
                  <ArrowDownIcon aria-hidden="true" className="mx-auto mb-2 text-muted-foreground" />
                  <ol className="grid gap-4">
                    {branch.entries.map((entry, index) => (
                      <DecisionNode
                        key={entry.id}
                        entry={entry}
                        entriesById={entriesById}
                        isLast={index === branch.entries.length - 1}
                      />
                    ))}
                  </ol>
                </section>
              ))}
            </div>
          </div>
        ) : null}
      </FramePanel>
    </Frame>
  )
}
