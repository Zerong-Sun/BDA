import { createContext, useContext, useMemo, useState } from 'react'
import { StatusPill } from '../../components/ui/StatusPill'
import { AttachToGoalButton } from '../research/AttachToGoalButton'
import { Button } from '../../components/ui/Button'
import type { StatusTone } from '../../components/ui/statusTone'
import { useI18n } from '../../lib/i18n'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import {
  evidenceLanes,
  isUnbound,
  provenanceRefs,
  type TimelineEntry,
} from '../../lib/schemas/timeline'
import {
  buildDecisionTree,
  subtreeDecisionCount,
  type DecisionNode,
  type GoalNode,
} from './decisionTree'

/** What a card may do besides being read.
 *
 *  Passed through context rather than down every `GoalBranch`: the tree is recursive, so
 *  prop-drilling two values would touch every level for the benefit of the leaves. Absent
 *  means read-only, which is how the browser harness and the research panel render it. */
interface TreeActions {
  projectId: string
  onEdit: (entry: TimelineEntry) => void
}

const TreeActionsContext = createContext<TreeActions | null>(null)

/**
 * The decision tree: goals down the page, the judgements that closed off options hung
 * off them, and - the part that makes it a decision tree rather than a flowchart - the
 * branches that were rejected, with why.
 *
 * Three rules this view exists to enforce visually:
 *   1. a decision with no resolvable evidence is *marked*, not rendered as if it were
 *      settled (`isUnbound`);
 *   2. a refuted decision carries the strongest weight on the page, because a frozen
 *      negative result is the thing most likely to be re-opened by someone who cannot
 *      see why it was closed;
 *   3. a `both`-lane decision shows both lane marks, since the dry/wet join is the
 *      whole reason these live on one tree.
 */

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

function LaneMarks({ entry }: { entry: TimelineEntry }) {
  const { t } = useI18n()
  const tl = t.timeline
  const claimed = entry.lane
  const actual = evidenceLanes(entry)
  if (claimed === 'unspecified') return null

  const marks = claimed === 'both' ? (['dry', 'wet'] as const) : ([claimed] as const)
  return (
    <span className="inline-flex items-center gap-1">
      {marks.map((mark) => (
        <span
          key={mark}
          className="rounded border border-border-soft px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-secondary"
        >
          {mark === 'dry' ? tl.laneDry : tl.laneWet}
        </span>
      ))}
      {/* The lane is a claim; the provenance is what is actually there. Saying so beats
          quietly rendering a wet decision whose only evidence is a scheduler id. */}
      {(claimed === 'wet' || claimed === 'both') && !actual.wet ? (
        <span className="text-[10px] text-warning" title={tl.laneEvidenceMismatchHelp}>
          {tl.laneEvidenceMismatch}
        </span>
      ) : null}
    </span>
  )
}

function DecisionCard({ node }: { node: DecisionNode }) {
  const actions = useContext(TreeActionsContext)
  const { t, format } = useI18n()
  const tl = t.timeline
  const [open, setOpen] = useState(false)
  const entry = node.entry
  const refs = provenanceRefs(entry)
  const unbound = isUnbound(entry)

  return (
    <li
      className={`rounded-md border-l-4 bg-bg-app py-2 pl-3 pr-2 ${
        entry.outcome === 'refuted' ? 'border-l-danger' : 'border-l-border-soft'
      }`}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        {entry.decision_ref ? (
          <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-text-primary">
            {entry.decision_ref}
          </span>
        ) : null}
        <StatusPill
          label={tl.outcome[entry.outcome as keyof typeof tl.outcome] ?? entry.outcome}
          tone={outcomeTone(entry.outcome)}
        />
        <LaneMarks entry={entry} />
        <time className="font-mono text-[11px] text-text-muted" dateTime={entry.occurred_at}>
          {entry.occurred_at.slice(0, 10)}
        </time>
      </div>

      <p className="mt-1 text-sm font-medium text-text-primary">{entry.title}</p>
      {entry.summary ? <p className="mt-0.5 text-xs text-text-secondary">{entry.summary}</p> : null}

      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px]">
        {unbound ? (
          <span className="rounded bg-warning-bg px-1.5 py-0.5 text-warning" title={tl.unboundHelp}>
            {tl.unbound}
          </span>
        ) : (
          <span className="text-text-muted">{format(tl.evidenceCount, { count: String(refs.length) })}</span>
        )}
        {node.superseded.length ? (
          <span className="text-text-muted">
            {format(tl.supersedesCount, { count: String(node.superseded.length) })}
          </span>
        ) : null}
        {entry.alternatives.length || node.superseded.length || entry.body ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-0 py-0 text-[11px]"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? tl.hideDetail : tl.showDetail}
          </Button>
        ) : null}
        {actions ? (
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-auto px-0 py-0 text-[11px]"
              onClick={() => actions.onEdit(entry)}
            >
              {tl.editorEdit}
            </Button>
            {/* The tree is the default view, so the control that moves a decision out of
                "not attached to any goal" has to be reachable from here - offering it
                only on the timeline tab would leave the fix one tab away from the
                problem it fixes. */}
            <AttachToGoalButton
              projectId={actions.projectId}
              resourceType="timeline_entry"
              resourceId={entry.id}
            />
          </>
        ) : null}
      </div>

      {open ? (
        <div className="mt-2 space-y-2">
          {entry.alternatives.length ? (
            <div className="rounded-md border border-border-soft bg-surface-2 p-2">
              <p className="text-[11px] uppercase tracking-wide text-text-muted">{tl.alternatives}</p>
              <ul className="mt-1 space-y-1">
                {entry.alternatives.map((alternative) => (
                  <li key={alternative.option} className="text-xs">
                    <span className="text-text-primary line-through decoration-text-muted">
                      {alternative.option}
                    </span>
                    <span className="text-text-secondary"> — {alternative.rejected_because}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {node.superseded.length ? (
            <ul className="space-y-1">
              {node.superseded.map((older) => (
                <li key={older.id} className="text-xs text-text-muted">
                  ↩ {older.decision_ref ? `${older.decision_ref} · ` : ''}
                  {older.title}
                </li>
              ))}
            </ul>
          ) : null}
          {entry.body ? (
            <div className="whitespace-pre-wrap rounded-md border border-border-soft bg-surface-2 p-2 text-xs text-text-secondary">
              {entry.body}
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}

function GoalBranch({ node }: { node: GoalNode }) {
  const { t, format } = useI18n()
  const tl = t.timeline
  const count = subtreeDecisionCount(node)
  return (
    <li style={{ marginInlineStart: node.depth ? '1.25rem' : undefined }}>
      <div className="flex flex-wrap items-baseline gap-2 border-l-2 border-l-accent pl-2">
        <h3 className="text-sm font-semibold text-text-primary">{node.goal.title}</h3>
        <span className="text-[11px] text-text-muted">
          {format(tl.decisionCount, { count: String(count) })}
        </span>
      </div>
      {node.decisions.length ? (
        <ul className="mt-1.5 space-y-1.5 pl-2">
          {node.decisions.map((decision) => (
            <DecisionCard key={decision.entry.id} node={decision} />
          ))}
        </ul>
      ) : null}
      {node.children.length ? (
        <ul className="mt-2 space-y-3">
          {node.children.map((child) => (
            <GoalBranch key={child.goal.id} node={child} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

interface DecisionTreeViewProps {
  goals: ResearchGoal[]
  entries: TimelineEntry[]
  /** Omit to render the tree read-only. */
  actions?: TreeActions
}

export function DecisionTreeView({ goals, entries, actions }: DecisionTreeViewProps) {
  const { t } = useI18n()
  const tl = t.timeline
  const tree = useMemo(() => buildDecisionTree(goals, entries), [goals, entries])

  if (!tree.roots.length && !tree.unattached.length) {
    return <p className="text-sm text-text-secondary">{tl.treeEmpty}</p>
  }

  return (
    <TreeActionsContext.Provider value={actions ?? null}>
    <div className="space-y-5">
      {tree.roots.length ? (
        <ul className="space-y-4">
          {tree.roots.map((node) => (
            <GoalBranch key={node.goal.id} node={node} />
          ))}
        </ul>
      ) : null}

      {tree.unattached.length ? (
        <section>
          <h3 className="mb-1 text-xs uppercase tracking-wide text-text-muted">{tl.unattached}</h3>
          <p className="mb-2 text-xs text-text-secondary">{tl.unattachedHelp}</p>
          <ul className="space-y-1.5">
            {tree.unattached.map((decision) => (
              <DecisionCard key={decision.entry.id} node={decision} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
    </TreeActionsContext.Provider>
  )
}
