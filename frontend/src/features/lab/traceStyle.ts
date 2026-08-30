/**
 * How the nth trace in a chart is drawn.
 *
 * Its own module because the chart component must export only components for
 * fast refresh to work, and because the legend and the line both read it —
 * deriving both from one function is what keeps them from disagreeing.
 *
 * There are five theme chart colours and a BLI run can carry eight
 * concentrations, so the ramp wraps into a dashed stroke rather than repeating
 * a solid one: two curves that look identical are worse than one drawn dashed.
 */

const RAMP = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
]

const DASHES = ['none', '5 3', '1 2']

export function traceStyle(index: number): { stroke: string; dash: string } {
  return {
    stroke: RAMP[index % RAMP.length],
    dash: DASHES[Math.floor(index / RAMP.length) % DASHES.length],
  }
}
