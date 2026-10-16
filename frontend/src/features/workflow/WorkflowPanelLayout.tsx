import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { useI18n } from '../../lib/i18n'
import './workflowWorkspace.css'

const storageKey = 'bda.workflow-panel-widths.v1'
const defaults = { resources: 260, inspector: 340 }
type Panel = keyof typeof defaults
const minimum = { resources: 220, inspector: 280 }

function readWidths() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) ?? '{}')
    return Object.fromEntries(Object.entries(defaults).map(([key, fallback]) => [
      key, typeof saved?.[key] === 'number' && Number.isFinite(saved[key])
        ? Math.max(minimum[key as Panel], Math.min(480, saved[key])) : fallback,
    ])) as typeof defaults
  } catch {
    return defaults
  }
}

/** Explicit grid areas keep responsive ordering independent of utility extraction. */
export function WorkflowPanelLayout({ overview, children }: { overview: boolean; children: ReactNode }) {
  const { language } = useI18n()
  const [widths, setWidths] = useState(readWidths)
  const root = useRef<HTMLDivElement>(null)
  const drag = useRef<{ panel: Panel; x: number; width: number } | null>(null)

  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(widths)) } catch { /* Storage can be disabled. */ }
  }, [widths])

  const resize = (panel: Panel, width: number) => {
    const containerWidth = root.current?.getBoundingClientRect().width ?? 1440
    const maximum = Math.max(minimum[panel], Math.min(480, containerWidth * (panel === 'resources' ? 0.25 : 0.32)))
    setWidths(current => ({ ...current, [panel]: Math.round(Math.max(minimum[panel], Math.min(maximum, width))) }))
  }

  return <div ref={root} className="workflow-workspace" data-overview={overview}
    style={{ '--workflow-resources-width': `${widths.resources}px`, '--workflow-inspector-width': `${widths.inspector}px` } as CSSProperties}>
    {children}
    {(['resources', 'inspector'] as const).map(panel => <div
      key={panel}
      className={`workflow-divider workflow-divider--${panel}`}
      role="separator" tabIndex={0} aria-orientation="vertical"
      aria-label={language === 'zh' ? (panel === 'resources' ? '调整资源栏宽度' : '调整详情面板宽度') : (panel === 'resources' ? 'Resize resource sidebar' : 'Resize inspector')}
      aria-valuemin={minimum[panel]} aria-valuemax={480} aria-valuenow={widths[panel]}
      onPointerDown={event => {
        if (event.button !== 0) return
        event.preventDefault()
        const width = root.current?.querySelector(`[data-workflow-panel="${panel}"]`)?.getBoundingClientRect().width ?? widths[panel]
        drag.current = { panel, x: event.clientX, width }
        event.currentTarget.setPointerCapture(event.pointerId)
      }}
      onPointerMove={event => {
        if (!drag.current || drag.current.panel !== panel) return
        resize(panel, drag.current.width + (event.clientX - drag.current.x) * (panel === 'resources' ? 1 : -1))
      }}
      onPointerUp={event => {
        drag.current = null
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
      }}
      onLostPointerCapture={() => { drag.current = null }}
      onPointerCancel={() => { drag.current = null }}
      onDoubleClick={() => resize(panel, defaults[panel])}
      onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
        event.preventDefault()
        const step = (event.shiftKey ? 40 : 20) * (panel === 'resources' ? 1 : -1)
        resize(panel, event.key === 'Home' ? minimum[panel] : event.key === 'End' ? 480 : widths[panel] + (event.key === 'ArrowRight' ? step : -step))
      }}
    ><span aria-hidden="true" /></div>)}
  </div>
}
