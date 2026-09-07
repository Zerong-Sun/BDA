import { Button } from '../../components/ui/Button'
import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react'
import { themeColor } from '../../lib/theme/themeColor'

export function WorkflowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  label,
  data,
  markerEnd,
  style,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke:
            label === 'feedback'
              ? themeColor('--accent-2', '#D89A3A')
              : themeColor('--accent', '#D08A2A'),
          strokeWidth: label === 'feedback' ? 2 : 1.5,
          ...style,
        }}
      />
      <EdgeLabelRenderer>
        <Button
          type="button"
          disabled={typeof data?.onSelect !== 'function'}
          variant="outline"
          className="nodrag nopan pointer-events-auto absolute rounded-full border border-border-soft bg-surface-1 px-2 py-1 text-[10px] text-text-primary shadow-sm"
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)` }}
          onClick={() => (data?.onSelect as (() => void) | undefined)?.()}
          aria-label={String(data?.gateLabel ?? label ?? 'Configure gate')}
        >
          {String(data?.gateLabel ?? label ?? 'Configure gate')}
        </Button>
      </EdgeLabelRenderer>
    </>
  )
}
