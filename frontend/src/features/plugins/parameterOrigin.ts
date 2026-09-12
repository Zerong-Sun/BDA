import type { ParameterFieldDefinition } from '../../lib/forms/parameterSchema'

/**
 * Where the number in front of you came from.
 *
 * A parameter form shows values with no account of their authorship: the plugin's default,
 * a route the copilot proposed, something the environment fixes, and something you typed
 * all render identically. That is the wrong thing to hide from someone deciding whether to
 * override it - and it is the cheapest half of agent transparency to provide, because it
 * is one word per field rather than an explanation.
 *
 * Deliberately one line and not a rationale. A reader deciding whether to touch a value
 * needs to know whose value it is; if they want the reasoning they can ask for it. A form
 * that argued its case on every field would be read the way a long consent dialog is read.
 */

export type ParameterOrigin =
  /** The schema's own default. Nobody chose this for this run. */
  | 'default'
  /** Proposed for this run - by a route plan, a copilot recommendation, a prior campaign. */
  | 'recommended'
  /** Set by whoever is editing, differing from every source above. */
  | 'edited'
  /** Fixed by something outside this form; changing it here desynchronises the two. */
  | 'constrained'

export interface ParameterOriginSources {
  /** Values proposed for this particular run. */
  recommended?: Record<string, unknown>
  /**
   * Values the environment pins. On this platform that is the cluster: a plugin's declared
   * `cpus` drives `-n`, `span[ptile]` and the thread count the tool is told to use, and
   * those three must agree. A form that let one of them drift on its own would be
   * producing the exact mismatch the project treats as a violation rather than a notice.
   */
  constrained?: Record<string, unknown>
}

const same = (a: unknown, b: unknown): boolean =>
  a === b || JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

export function parameterOrigin(
  field: ParameterFieldDefinition,
  value: unknown,
  sources: ParameterOriginSources = {},
): ParameterOrigin {
  // Constraint first: if the environment pins a value, that is true whether or not the
  // value also happens to equal the default, and it is the fact that changes what the
  // reader should do about it.
  if (sources.constrained && field.key in sources.constrained) return 'constrained'
  if (sources.recommended && same(value, sources.recommended[field.key])) return 'recommended'
  if (same(value, field.default)) return 'default'
  return 'edited'
}

/**
 * The parameters a plugin's declared resources pin.
 *
 * Only the thread-count family, and only when the plugin actually declares `cpus`. A
 * plugin that has not declared anything constrains nothing, and claiming otherwise would
 * put a badge on a field nobody is bound by - which is how a transparency signal stops
 * being read.
 */
const THREAD_KEYS = ['cpus', 'cpu', 'n_cpu', 'nproc', 'threads', 'num_threads', 'n_threads']

export function clusterConstrainedParameters(
  resources: Record<string, unknown> | undefined,
  fields: ParameterFieldDefinition[],
): Record<string, unknown> {
  const declared = resources?.cpus
  if (typeof declared !== 'number' || declared <= 0) return {}
  const pinned: Record<string, unknown> = {}
  for (const field of fields) {
    if (THREAD_KEYS.includes(field.key.toLowerCase())) pinned[field.key] = declared
  }
  return pinned
}
