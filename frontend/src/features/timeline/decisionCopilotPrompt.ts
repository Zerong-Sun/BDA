import { provenanceRefs, type TimelineEntry } from '../../lib/schemas/timeline'

/** The words around the record. Supplied already localized and already formatted, so this
 *  module holds the shape of the question and none of the copy. */
export interface DecisionPromptCopy {
  intro: string
  evidenceRule: string
  output: string
  evidenceLabel: string
  outcomeHeading: string
  outcomeLabel: string
}

/**
 * The question to hand the Copilot when a reader asks what a recorded decision means.
 *
 * The decision's own text is carried *in the question* rather than referenced by id.
 * `copilot/research_context.py` flattens findings, references, datasets, structures and
 * literature excerpts into the searchable item set and knows nothing about
 * `project_timeline_entries`, so selecting this row as a Copilot entity would filter to
 * nothing and ground the answer in no evidence at all - worse than asking plainly.
 *
 * Empty fields are dropped rather than sent as blank headings: a decision with no body
 * should not produce a prompt containing an empty section for the model to fill in.
 *
 * Lives outside both card components because the timeline list and the decision tree each
 * offer this control, and a component file may export only components.
 */
export function buildDecisionCopilotPrompt(entry: TimelineEntry, copy: DecisionPromptCopy): string {
  const evidence = provenanceRefs(entry)
    .map((ref) => `${ref.kind}:${ref.value}`)
    .join(', ')
  return [
    copy.intro,
    [entry.decision_ref, entry.title].filter(Boolean).join(' · '),
    entry.summary,
    entry.body,
    entry.outcome === 'unspecified' ? '' : `${copy.outcomeHeading}: ${copy.outcomeLabel}`,
    evidence ? `${copy.evidenceLabel}: ${evidence}` : '',
    copy.evidenceRule,
    copy.output,
  ]
    .filter(Boolean)
    .join('\n\n')
}
