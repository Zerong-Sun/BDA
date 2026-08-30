import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listAllTimeline } from '../../lib/api/timeline'
import {
  TIMELINE_ENTRY_TYPES,
  TIMELINE_OUTCOMES,
  groupByPhase,
  provenanceRefs,
  type TimelineEntry,
} from '../../lib/schemas/timeline'
import { AppFrame } from '../../components/ui/AppFrame'
import { StatusPill } from '../../components/ui/StatusPill'
import { Button } from '../../components/ui/Button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import type { StatusTone } from '../../components/ui/statusTone'
import { useI18n } from '../../lib/i18n'

/** Radix Select cannot hold an empty-string value, so 'all' and the unphased bucket
 *  get explicit sentinels rather than being smuggled through ''. */
const ALL = '__all__'
const NO_PHASE = '__nophase__'

interface ProjectTimelineProps {
  projectId: string
}

/** Outcome maps onto the shared StatusPill vocabulary rather than raw colours, so the
 *  timeline stays consistent with how status is shown everywhere else in the app (and
 *  so the design-system audit stays green). A refuted result is the most valuable row on
 *  the page - it must not look identical to an open one. */
function outcomeTone(outcome: string): StatusTone {
  switch (outcome) {
    case 'supported':
      return 'green'
    case 'refuted':
      return 'red'
    case 'inconclusive':
      return 'amber'
    default:
      return 'neutral'
  }
}

/** Left rule uses semantic border tokens only. `border-accent` marks the entries a
 *  reader should stop at (settled either way); open items stay quiet. */
function outcomeRule(outcome: string): string {
  return outcome === 'unspecified' ? 'border-l-border-soft' : 'border-l-accent'
}

function EntryCard({ entry }: { entry: TimelineEntry }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const tl = t.timeline
  const refs = provenanceRefs(entry)
  const typeLabel = tl.type[entry.entry_type as keyof typeof tl.type] ?? entry.entry_type
  const outcomeLabel = tl.outcome[entry.outcome as keyof typeof tl.outcome] ?? entry.outcome

  return (
    <li className={`relative border-l-4 ${outcomeRule(entry.outcome)} bg-bg-app pl-4 pr-3 py-3 rounded-r-md`}>
      <div className="flex flex-wrap items-baseline gap-2">
        <time className="font-mono text-xs text-text-secondary" dateTime={entry.occurred_at}>
          {entry.occurred_at.slice(0, 16).replace('T', ' ')}
        </time>
        <span className="rounded-full border border-border-soft px-2 py-0.5 text-[10px] uppercase tracking-wide text-text-secondary">
          {typeLabel}
        </span>
        <StatusPill label={outcomeLabel} tone={outcomeTone(entry.outcome)} />
      </div>

      <h3 className="mt-1 font-semibold text-text-primary">{entry.title}</h3>
      {entry.summary ? <p className="mt-1 text-sm text-text-secondary">{entry.summary}</p> : null}

      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-muted">
        {entry.supersedes_id ? <span title={entry.supersedes_id}>↩ {tl.supersedes}</span> : null}
        {entry.caused_by_id ? <span title={entry.caused_by_id}>⤷ {tl.causedBy}</span> : null}
        {entry.tags.map((tag) => (
          <span key={tag} className="rounded bg-surface-2 px-1.5 py-0.5">
            #{tag}
          </span>
        ))}
      </div>

      {entry.body ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-2 px-0 text-xs"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
        >
          {open ? tl.hideDetail : tl.showDetail}
        </Button>
      ) : null}

      {open ? (
        <div className="mt-2 whitespace-pre-wrap rounded-md border border-border-soft bg-surface-2 p-3 text-xs text-text-secondary">
          {entry.body}
        </div>
      ) : null}

      {refs.length || entry.code_refs.length ? (
        <div className="mt-2 grid gap-2 text-[11px] md:grid-cols-2">
          {refs.length ? (
            <div>
              <p className="text-text-muted">{tl.evidence}</p>
              <ul className="mt-1 space-y-0.5">
                {refs.map((ref) => (
                  <li key={`${ref.kind}:${ref.value}`} className="font-mono text-text-secondary">
                    <span className="text-text-muted">{ref.kind}</span> {ref.value}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {entry.code_refs.length ? (
            <div>
              <p className="text-text-muted">{tl.code}</p>
              <ul className="mt-1 space-y-0.5">
                {entry.code_refs.map((ref) => (
                  <li key={ref.path} className="text-text-secondary">
                    <span className="font-mono">{ref.path}</span>
                    {ref.role ? <span className="text-text-muted"> — {ref.role}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}

export function ProjectTimeline({ projectId }: ProjectTimelineProps) {
  const { t, format } = useI18n()
  const tl = t.timeline
  const [phase, setPhase] = useState('')
  const [entryType, setEntryType] = useState('')
  const [outcome, setOutcome] = useState('')

  const query = useQuery({
    queryKey: ['project-timeline', projectId],
    queryFn: () => listAllTimeline(projectId),
    staleTime: 60_000,
  })

  const entries = useMemo(() => query.data ?? [], [query.data])
  const phases = useMemo(
    () => Array.from(new Set(entries.map((entry) => entry.phase))),
    [entries],
  )

  // Filtering client-side because the whole timeline is already loaded; going back to
  // the server for each filter change would be slower and no more correct.
  const visible = useMemo(
    () =>
      entries.filter(
        (entry) =>
          (!phase || entry.phase === phase || (phase === NO_PHASE && !entry.phase)) &&
          (!entryType || entry.entry_type === entryType) &&
          (!outcome || entry.outcome === outcome),
      ),
    [entries, phase, entryType, outcome],
  )

  const grouped = useMemo(() => groupByPhase(visible), [visible])

  if (query.isLoading) {
    return (
      <AppFrame panelClassName="p-4 text-sm text-text-secondary">{tl.loading}</AppFrame>
    )
  }
  if (query.isError) {
    return <AppFrame panelClassName="p-4 text-sm text-text-secondary">{tl.loadFailed}</AppFrame>
  }
  if (!entries.length) {
    return <AppFrame panelClassName="p-4 text-sm text-text-secondary">{tl.empty}</AppFrame>
  }

  return (
    <AppFrame panelClassName="p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">{tl.title}</h2>
          <p className="text-sm text-text-secondary">{tl.subtitle}</p>
        </div>
        <span className="text-xs text-text-muted">
          {format(tl.entryCount, { count: String(visible.length) })}
        </span>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <Select value={phase || ALL} onValueChange={(value) => setPhase(value === ALL ? '' : (value ?? ''))}>
          <SelectTrigger aria-label={tl.allPhases} className="min-w-36">
            <SelectValue placeholder={tl.allPhases} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{tl.allPhases}</SelectItem>
            {phases.map((value) => (
              <SelectItem key={value || '_'} value={value || NO_PHASE}>
                {value || tl.noPhase}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={entryType || ALL} onValueChange={(value) => setEntryType(value === ALL ? '' : (value ?? ''))}>
          <SelectTrigger aria-label={tl.allTypes} className="min-w-36">
            <SelectValue placeholder={tl.allTypes} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{tl.allTypes}</SelectItem>
            {TIMELINE_ENTRY_TYPES.map((value) => (
              <SelectItem key={value} value={value}>
                {tl.type[value]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={outcome || ALL} onValueChange={(value) => setOutcome(value === ALL ? '' : (value ?? ''))}>
          <SelectTrigger aria-label={tl.allOutcomes} className="min-w-36">
            <SelectValue placeholder={tl.allOutcomes} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{tl.allOutcomes}</SelectItem>
            {TIMELINE_OUTCOMES.map((value) => (
              <SelectItem key={value} value={value}>
                {tl.outcome[value]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-5">
        {grouped.map((group) => (
          <section key={group.phase || '_'}>
            <h3 className="mb-2 text-xs uppercase tracking-wide text-accent">
              {group.phase || tl.noPhase}
            </h3>
            <ol className="space-y-2">
              {group.entries.map((entry) => (
                <EntryCard key={entry.id} entry={entry} />
              ))}
            </ol>
          </section>
        ))}
      </div>
    </AppFrame>
  )
}
