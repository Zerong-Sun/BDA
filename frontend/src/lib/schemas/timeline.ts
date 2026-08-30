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

export const CodeRefSchema = z.object({
  path: z.string(),
  role: z.string().default(''),
})

export const TimelineEntrySchema = z.object({
  id: z.string(),
  project_id: z.string(),
  occurred_at: z.string(),
  entry_type: z.enum(TIMELINE_ENTRY_TYPES),
  phase: z.string(),
  title: z.string(),
  summary: z.string(),
  body: z.string(),
  outcome: z.enum(TIMELINE_OUTCOMES),
  provenance: z.record(z.string(), z.unknown()),
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
