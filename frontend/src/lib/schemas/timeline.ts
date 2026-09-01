import { z } from 'zod'

/** Kept in step with backend `app/timeline/models.py`; a value outside these is a bug
 *  on one side or the other, so parsing is strict rather than permissive. */
export const TIMELINE_ENTRY_TYPES = [
  'plan',
  'decision',
  'problem',
  'resolution',
  'result',
  'method',
  'milestone',
] as const

export const TIMELINE_OUTCOMES = ['supported', 'refuted', 'inconclusive', 'unspecified'] as const

/** Which half of the loop an entry belongs to. `both` is the interesting one: a decision
 *  whose evidence is on one side and whose consequence is on the other. */
export const TIMELINE_LANES = ['dry', 'wet', 'both', 'unspecified'] as const

export type TimelineLane = (typeof TIMELINE_LANES)[number]

/** The provenance keys that point at bench work. The backend requires one of them on a
 *  wet-lane decision; the UI uses the same set to say which half a row's evidence is in. */
export const WET_PROVENANCE_KEYS = ['experiment_result_ids', 'protein_ids'] as const

export const AlternativeSchema = z.object({
  option: z.string(),
  rejected_because: z.string(),
})

export const CodeRefSchema = z.object({
  path: z.string(),
  role: z.string().default(''),
})

export const TimelineEntrySchema = z.object({
  id: z.string(),
  project_id: z.string(),
  occurred_at: z.string(),
  entry_type: z.enum(TIMELINE_ENTRY_TYPES),
  decision_ref: z.string().nullable().default(null),
  lane: z.enum(TIMELINE_LANES).default('unspecified'),
  phase: z.string(),
  title: z.string(),
  summary: z.string(),
  body: z.string(),
  outcome: z.enum(TIMELINE_OUTCOMES),
  provenance: z.record(z.string(), z.unknown()),
  alternatives: z.array(AlternativeSchema).default([]),
  code_refs: z.array(CodeRefSchema),
  supersedes_id: z.string().nullable(),
  caused_by_id: z.string().nullable(),
  tags: z.array(z.string()),
  created_by: z.string().nullable(),
  version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type TimelineEntry = z.infer<typeof TimelineEntrySchema>
export type CodeRef = z.infer<typeof CodeRefSchema>
export type Alternative = z.infer<typeof AlternativeSchema>

export const TimelineEntryPageSchema = z.object({
  items: z.array(TimelineEntrySchema),
  next_cursor: z.string().nullable().optional(),
})

export type TimelineEntryPage = z.infer<typeof TimelineEntryPageSchema>

/** Flatten `provenance` into a display list. The backend stores identifiers by kind;
 *  the UI wants one labelled list, and callers should not each re-derive it. */
export function provenanceRefs(entry: TimelineEntry): Array<{ kind: string; value: string }> {
  const out: Array<{ kind: string; value: string }> = []
  for (const [kind, value] of Object.entries(entry.provenance)) {
    if (!Array.isArray(value)) continue
    for (const item of value) {
      if (typeof item === 'string') out.push({ kind, value: item })
    }
  }
  return out
}

/** Group a chronological list into phases, preserving order of first appearance so the
 *  timeline still reads as a timeline rather than being alphabetised by phase name. */
export function groupByPhase(entries: TimelineEntry[]): Array<{ phase: string; entries: TimelineEntry[] }> {
  const groups: Array<{ phase: string; entries: TimelineEntry[] }> = []
  for (const entry of entries) {
    const existing = groups.find((group) => group.phase === entry.phase)
    if (existing) existing.entries.push(entry)
    else groups.push({ phase: entry.phase, entries: [entry] })
  }
  return groups
}

/** A decision whose conclusion rests on nothing the platform can resolve.
 *
 *  Deliberately shown rather than hidden. Of the 105 entries the two seeders write, the
 *  provenance field is filled 50 times and 49 of those are opaque scheduler ids - so the
 *  record reads as complete while pointing at almost nothing. A row marked unbound is a
 *  row someone can fix; a row that renders identically to a well-evidenced one is not.
 *  Only `decision` is judged: a plan is written before the evidence exists. */
export function isUnbound(entry: TimelineEntry): boolean {
  if (entry.entry_type !== 'decision') return false
  return provenanceRefs(entry).length === 0
}

/** Which halves of the loop this entry's *evidence* actually sits in.
 *
 *  Distinct from `lane`, which is a claim about the decision. When the two disagree -
 *  a `wet` lane with only job ids under it - that is worth seeing, not smoothing over. */
export function evidenceLanes(entry: TimelineEntry): { dry: boolean; wet: boolean } {
  const refs = provenanceRefs(entry)
  const wetKeys = new Set<string>(WET_PROVENANCE_KEYS)
  return {
    dry: refs.some((ref) => !wetKeys.has(ref.kind)),
    wet: refs.some((ref) => wetKeys.has(ref.kind)),
  }
}

/** The open branches: decisions nobody has settled, and that nothing supersedes.
 *
 *  This is what NEXT_PLAN should be derived from rather than written a second time by
 *  hand. Sorted newest first, because an open question raised today is the one being
 *  worked on. */
export function openQuestions(entries: TimelineEntry[]): TimelineEntry[] {
  const superseded = new Set(entries.map((entry) => entry.supersedes_id).filter(Boolean) as string[])
  return entries
    .filter(
      (entry) =>
        entry.entry_type === 'decision' &&
        entry.outcome === 'unspecified' &&
        !superseded.has(entry.id),
    )
    .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at))
}
