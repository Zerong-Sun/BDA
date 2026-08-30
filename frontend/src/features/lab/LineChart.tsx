import { useId, useMemo } from 'react'
import type { Series } from '../../lib/schemas/instrumentAnalysis'
import { traceStyle } from './traceStyle'

/**
 * A line chart, in SVG, with no charting dependency.
 *
 * The backend deliberately has no plotting library — kernels return data and
 * the drawing happens here — so this is the piece that has to exist for that
 * split to pay off. It is small because a sensorgram and a chromatogram need
 * the same three things: shared axes across several traces, a readable scale,
 * and nothing that invents a point.
 *
 * Stroke and dash come from `traceStyle`, which the legend below reads too, so
 * a line and its key cannot disagree.
 */

export interface Trace {
  label: string
  points: Series
}

function niceNumber(value: number): string {
  if (!Number.isFinite(value)) return '—'
  const magnitude = Math.abs(value)
  if (magnitude !== 0 && (magnitude < 0.01 || magnitude >= 100000)) return value.toExponential(1)
  return String(Math.round(value * 100) / 100)
}

export function LineChart({
  traces,
  xLabel,
  yLabel,
  height = 220,
  bands = [],
  markers = [],
  ariaLabel,
}: {
  traces: Trace[]
  xLabel: string
  yLabel: string
  height?: number
  /** Shaded x-ranges: collected fractions, or an association phase. */
  bands?: { start: number; end: number; label?: string }[]
  /** Vertical rules: detected peak apexes. */
  markers?: { at: number; label?: string }[]
  ariaLabel: string
}) {
  const clipId = useId()
  const width = 640
  const padding = { top: 12, right: 12, bottom: 34, left: 52 }

  const bounds = useMemo(() => {
    const xs: number[] = []
    const ys: number[] = []
    for (const trace of traces) {
      for (const [x, y] of trace.points) {
        xs.push(x)
        ys.push(y)
      }
    }
    if (xs.length === 0) return null
    const xMin = Math.min(...xs)
    const xMax = Math.max(...xs)
    const yMin = Math.min(...ys)
    const yMax = Math.max(...ys)
    // A flat trace has no range to scale against; give it one so the line lands
    // in the middle of the plot instead of dividing by zero.
    const xSpan = xMax - xMin || 1
    const ySpan = yMax - yMin || 1
    return { xMin, xMax, yMin, yMax, xSpan, ySpan }
  }, [traces])

  if (!bounds) return null

  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const toX = (value: number) => padding.left + ((value - bounds.xMin) / bounds.xSpan) * plotWidth
  const toY = (value: number) =>
    padding.top + plotHeight - ((value - bounds.yMin) / bounds.ySpan) * plotHeight

  const yTicks = [bounds.yMin, bounds.yMin + bounds.ySpan / 2, bounds.yMax]
  const xTicks = [bounds.xMin, bounds.xMin + bounds.xSpan / 2, bounds.xMax]

  return (
    <div className="space-y-2">
      <svg
        role="img"
        aria-label={ariaLabel}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ maxHeight: height }}
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={padding.left} y={padding.top} width={plotWidth} height={plotHeight} />
          </clipPath>
        </defs>
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={toY(tick)}
              y2={toY(tick)}
              stroke="currentColor"
              strokeOpacity={0.12}
            />
            <text
              x={padding.left - 6}
              y={toY(tick)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={10}
              fill="currentColor"
              fillOpacity={0.6}
            >
              {niceNumber(tick)}
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <text
            key={`x-${tick}`}
            x={toX(tick)}
            y={height - padding.bottom + 14}
            textAnchor="middle"
            fontSize={10}
            fill="currentColor"
            fillOpacity={0.6}
          >
            {niceNumber(tick)}
          </text>
        ))}
        <g clipPath={`url(#${clipId})`}>
          {bands.map((band, index) => (
            <rect
              key={`band-${index}`}
              x={toX(band.start)}
              y={padding.top}
              width={Math.max(toX(band.end) - toX(band.start), 1)}
              height={plotHeight}
              fill="currentColor"
              fillOpacity={0.06}
            />
          ))}
          {markers.map((marker, index) => (
            <line
              key={`marker-${index}`}
              x1={toX(marker.at)}
              x2={toX(marker.at)}
              y1={padding.top}
              y2={padding.top + plotHeight}
              stroke="currentColor"
              strokeOpacity={0.35}
              strokeDasharray="3 3"
            />
          ))}
          {traces.map((trace, index) => (
            <polyline
              key={trace.label}
              fill="none"
              stroke={traceStyle(index).stroke}
              strokeDasharray={traceStyle(index).dash}
              strokeWidth={1.5}
              points={trace.points.map(([x, y]) => `${toX(x)},${toY(y)}`).join(' ')}
            />
          ))}
        </g>
        <text
          x={padding.left + plotWidth / 2}
          y={height - 2}
          textAnchor="middle"
          fontSize={10}
          fill="currentColor"
          fillOpacity={0.6}
        >
          {xLabel}
        </text>
        <text
          x={12}
          y={padding.top + plotHeight / 2}
          textAnchor="middle"
          fontSize={10}
          fill="currentColor"
          fillOpacity={0.6}
          transform={`rotate(-90 12 ${padding.top + plotHeight / 2})`}
        >
          {yLabel}
        </text>
      </svg>
      {traces.length > 1 ? (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
          {traces.map((trace, index) => (
            <li key={trace.label} className="flex items-center gap-1.5">
              <svg aria-hidden width={16} height={6} className="shrink-0">
                <line
                  x1={0}
                  x2={16}
                  y1={3}
                  y2={3}
                  stroke={traceStyle(index).stroke}
                  strokeDasharray={traceStyle(index).dash}
                  strokeWidth={2}
                />
              </svg>
              {trace.label}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
