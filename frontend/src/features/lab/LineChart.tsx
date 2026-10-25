import { useId, useMemo, useRef } from 'react'
import type { Series } from '../../lib/schemas/instrumentAnalysis'
import { traceStyle, type TraceKind } from './traceStyle'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'

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
  kind?: TraceKind
  colorIndex?: number
  opacity?: number
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
  const svgRef = useRef<SVGSVGElement>(null)
  const { language } = useI18n()
  const zh = language === 'zh'
  const kindLabel = (kind: TraceKind = 'measured') => ({ measured: zh ? '实测' : 'measured', fitted: zh ? '分析拟合' : 'analysis fit', 'instrument-fit': zh ? '仪器拟合' : 'instrument fit', simulated: zh ? '模拟' : 'simulated' })[kind]
  const exportSvg = () => {
    const original = svgRef.current
    if (!original) return
    const clone = original.cloneNode(true) as SVGSVGElement
    // Inline computed paints so the exact same chart remains readable outside the app/theme.
    const originals = [original, ...original.querySelectorAll('*')]
    const copies = [clone, ...clone.querySelectorAll('*')]
    originals.forEach((node, index) => {
      const style = getComputedStyle(node)
      for (const name of ['fill', 'stroke', 'color', 'font-family']) copies[index].setAttribute(name, style.getPropertyValue(name))
    })
    const legendHeight = traces.length * 16 + 20
    clone.setAttribute('viewBox', `0 0 ${width} ${height + legendHeight}`)
    clone.removeAttribute('class'); clone.removeAttribute('style')
    clone.setAttribute('width', String(width)); clone.setAttribute('height', String(height + legendHeight))
    const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    background.setAttribute('width', String(width)); background.setAttribute('height', String(height + legendHeight))
    background.setAttribute('fill', getComputedStyle(original).getPropertyValue('--bg-surface-1').trim() || '#ffffff')
    clone.insertBefore(background, clone.firstChild)
    traces.forEach((trace, index) => {
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('x', '52'); text.setAttribute('y', String(height + 18 + index * 16)); text.setAttribute('font-size', '11')
      text.setAttribute('fill', getComputedStyle(original).color)
      text.textContent = `${trace.label} · ${kindLabel(trace.kind)}`
      const swatch = document.createElementNS('http://www.w3.org/2000/svg', 'line')
      const line = original.querySelectorAll('[data-trace-kind]')[index]
      swatch.setAttribute('x1', '22'); swatch.setAttribute('x2', '44'); swatch.setAttribute('y1', String(height + 14 + index * 16)); swatch.setAttribute('y2', String(height + 14 + index * 16))
      swatch.setAttribute('stroke', line ? getComputedStyle(line).stroke : '#555')
      swatch.setAttribute('stroke-dasharray', traceStyle(trace.colorIndex ?? index, trace.kind).dash)
      swatch.setAttribute('stroke-opacity', String(trace.opacity ?? 1)); swatch.setAttribute('stroke-width', '2')
      clone.append(swatch, text)
    })
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: 'image/svg+xml' }))
    const link = document.createElement('a'); link.href = url; link.download = 'instrument-analysis.svg'; link.click(); URL.revokeObjectURL(url)
  }
  const width = 640
  const padding = { top: 12, right: 12, bottom: 34, left: 52 }

  const bounds = useMemo(() => {
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity
    for (const trace of traces) for (const [x, y] of trace.points) {
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue
      xMin = Math.min(xMin, x); xMax = Math.max(xMax, x)
      yMin = Math.min(yMin, y); yMax = Math.max(yMax, y)
    }
    if (!Number.isFinite(xMin)) return null
    if (xMin === xMax) { xMin -= 0.5; xMax += 0.5 }
    if (yMin === yMax) { yMin -= 0.5; yMax += 0.5 }
    return { xMin, xMax, yMin, yMax, xSpan: xMax - xMin, ySpan: yMax - yMin }
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
        ref={svgRef}
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
              key={`${trace.label}-${index}`}
              data-trace-kind={trace.kind ?? 'measured'}
              fill="none"
              stroke={traceStyle(trace.colorIndex ?? index, trace.kind).stroke}
              strokeDasharray={traceStyle(trace.colorIndex ?? index, trace.kind).dash}
              strokeOpacity={trace.opacity ?? 1}
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
      {traces.length > 0 ? (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
          {traces.map((trace, index) => (
            <li key={trace.label} className="flex items-center gap-1.5">
              <svg aria-hidden width={16} height={6} className="shrink-0">
                <line
                  x1={0}
                  x2={16}
                  y1={3}
                  y2={3}
                  stroke={traceStyle(trace.colorIndex ?? index, trace.kind).stroke}
                  strokeDasharray={traceStyle(trace.colorIndex ?? index, trace.kind).dash}
                  strokeOpacity={trace.opacity ?? 1}
                  strokeWidth={2}
                />
              </svg>
              {trace.label} · {kindLabel(trace.kind)}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-xs text-text-secondary">{zh ? '实测为实线，拟合为虚线；逐点连接，不作平滑。' : 'Measured traces are solid; fitted traces are dashed. Supplied points are connected without smoothing.'}</p>
      <Button type="button" size="sm" variant="outline" onClick={exportSvg}>{zh ? '导出 SVG 图表' : 'Export SVG chart'}</Button>
    </div>
  )
}
