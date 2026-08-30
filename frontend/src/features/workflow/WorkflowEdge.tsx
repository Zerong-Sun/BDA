import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react'
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
          stroke: label === 'feedback' ? themeColor('--accent-2', '#D89A3A') : themeColor('--accent', '#D08A2A'),
          strokeWidth: label === 'feedback' ? 2 : 1.5,
          ...style,
        }}
      />
      {label ? (
        <text
          x={labelX}
          y={labelY}
          className="fill-accent-2 text-[10px]"
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {label}
        </text>
      ) : null}
    </>
  )
}
