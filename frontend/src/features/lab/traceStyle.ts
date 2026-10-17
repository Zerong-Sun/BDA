/** Shared scientific plot semantics: color identifies a series; dash identifies its origin. */
export type TraceKind = 'measured' | 'fitted' | 'instrument-fit' | 'simulated'
const RAMP = [
  'var(--color-chart-1)', 'var(--color-chart-2)', 'var(--color-chart-3)',
  'var(--color-chart-4)', 'var(--color-chart-5)', '#0072b2', '#d55e00', '#009e73',
]
const DASHES: Record<TraceKind, string> = { measured: 'none', fitted: '6 3', 'instrument-fit': '2 3', simulated: '8 3 2 3' }
export function traceStyle(index: number, kind: TraceKind = 'measured'): { stroke: string; dash: string } {
  return { stroke: RAMP[index % RAMP.length], dash: DASHES[kind] }
}
