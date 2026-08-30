import { MarkerType } from '@xyflow/react'
import type {
  WorkflowEdge,
  WorkflowNode,
  WorkflowNodeStatus as ApiWorkflowNodeStatus,
} from '../../lib/schemas/workflow'
import { themeColor } from '../../lib/theme/themeColor'
import type { BdaWorkflowEdge, BdaWorkflowNode, WorkflowNodeData, WorkflowNodeStatus } from './workflowTypes'

const NODE_META: Record<
  string,
  { icon: string; resource: WorkflowNodeData['resource']; description?: string; column: number }
> = {
  target_intake: { icon: 'database', resource: 'local', column: 0 },
  backbone_generation: { icon: 'wand-sparkles', resource: 'gpu', column: 1 },
  sequence_generation: { icon: 'dna', resource: 'gpu', column: 2 },
  fold_prediction: { icon: 'scan-search', resource: 'gpu', column: 3 },
  workflow_pipeline: { icon: 'wand-sparkles', resource: 'gpu', column: 1 },
  scoring: { icon: 'activity', resource: 'cpu', column: 4 },
  selection: { icon: 'filter', resource: 'cpu', column: 5 },
  experiment: { icon: 'flask-conical', resource: 'manual', column: 6 },
  // Receptor-conditioned design route. Its stages are complex-level counterparts of the
  // single-chain ones above, so they need their own icons and resource classes rather
  // than the 'database'/'local' fallback an unknown node_type would otherwise get.
  interface_constraints: { icon: 'file-json', resource: 'local', column: 1 },
  complex_backbone_generation: { icon: 'wand-sparkles', resource: 'gpu', column: 2 },
  interface_sequence_design: { icon: 'dna', resource: 'gpu', column: 3 },
  complex_prediction: { icon: 'scan-search', resource: 'gpu', column: 4 },
  ensemble_docking: { icon: 'activity', resource: 'gpu', column: 5 },
  interface_physics_scoring: { icon: 'activity', resource: 'cpu', column: 6 },
  // De novo protocol routes A/B/C. Their prep, filter and free-energy stages have no
  // counterpart in the scaffold pipeline, and 'local data node' would misrepresent both
  // a metadynamics run and a go/no-go measurement.
  motif_extraction: { icon: 'file-json', resource: 'local', column: 2 },
  geometry_check: { icon: 'activity', resource: 'local', column: 0 },
  binder_generation: { icon: 'wand-sparkles', resource: 'gpu', column: 1 },
  ip_filter: { icon: 'filter', resource: 'cpu', column: 4 },
  linker_enumeration: { icon: 'dna', resource: 'cpu', column: 2 },
  differential_scoring: { icon: 'scan-search', resource: 'gpu', column: 3 },
  developability_filter: { icon: 'filter', resource: 'cpu', column: 2 },
  enhanced_sampling: { icon: 'activity', resource: 'gpu', column: 5 },
}

const COLUMN_WIDTH = 220
const ROW_HEIGHT = 140

/**
 * API node status to canvas status.
 *
 * The canvas keeps its own vocabulary because it has presentation-only states the API
 * has no concept of ('demo'). The previous version of this map was written against
 * 'staging'/'collecting_outputs'/'completed' - values a one-off seeding script emitted
 * and the compute pipeline never did - so real progress fell through to 'not_started'.
 *
 * Typing the record over the API union makes a new backend status a compile error here
 * rather than a silent 'not_started'.
 */
const CANVAS_STATUS: Record<ApiWorkflowNodeStatus, WorkflowNodeStatus> = {
  draft: 'not_started',
  pending: 'queued',
  dispatching: 'queued',
  queued: 'queued',
  running: 'running',
  collecting: 'running',
  succeeded: 'completed',
  failed: 'failed',
  cancelled: 'skipped',
  requires_review: 'requires_review',
}

function mapStatus(status: string): WorkflowNodeStatus {
  return CANVAS_STATUS[status as ApiWorkflowNodeStatus] ?? 'not_started'
}

function formatEstimateFooter(node: WorkflowNode): string | null {
  const parameters = node.parameters
  const planned = parameters.planned
  const current = parameters.current
  const unit = parameters.estimate_unit
  const time = parameters.estimated_time
  if (planned == null || current == null || typeof unit !== 'string') return null
  const progress = `${current}/${planned} ${unit}`
  return typeof time === 'string' ? `${progress} · ${time}` : progress
}

function parsePosition(node: WorkflowNode, index: number): { x: number; y: number } {
  const position = node.position
  if (position && typeof position.x === 'number' && typeof position.y === 'number') {
    return { x: position.x, y: position.y }
  }
  const meta = NODE_META[node.node_type] ?? { column: index, icon: 'database', resource: 'local' as const }
  return {
    x: 40 + meta.column * COLUMN_WIDTH,
    y: 80 + (index % 2) * ROW_HEIGHT,
  }
}

function missingPlugins(node: WorkflowNode): string[] {
  const declared = node.parameters.missing_model_plugins
  if (!Array.isArray(declared)) return []
  return declared.filter((item): item is string => typeof item === 'string' && item.length > 0)
}

export function footerFromMetrics(node: WorkflowNode): string {
  // A stage whose tool has no registered plugin cannot be dispatched at all, so that
  // outranks progress counts: '0/500 predictions' reads as 'not started yet' when the
  // truth is 'cannot start until someone registers AlphaFold-Multimer'.
  const missing = missingPlugins(node)
  if (missing.length > 0) return `Needs plugin: ${missing.join(', ')}`
  const metrics = typeof node.parameters.metrics === 'object' && node.parameters.metrics
    ? node.parameters.metrics as Record<string, unknown>
    : {}
  const parts: string[] = []
  if (metrics.backbone_count != null && metrics.sequences_per_backbone != null) {
    parts.push(`${metrics.backbone_count} backbones`)
    parts.push(`${metrics.sequences_per_backbone} seq/backbone`)
  }
  if (metrics.generated != null) parts.push(`${metrics.generated} generated`)
  if (metrics.designed != null) parts.push(`${metrics.designed} designed`)
  if (metrics.folded != null) parts.push(`${metrics.folded} folded`)
  if (metrics.scored != null) parts.push(`${metrics.scored} scored`)
  if (metrics.mean_plddt != null) parts.push(`${metrics.mean_plddt} mean pLDDT`)
  if (metrics.ordered != null) parts.push(`${metrics.ordered} ordered`)
  if (metrics.bli_positive != null) parts.push(`${metrics.bli_positive} BLI hits`)
  if (metrics.inputs_confirmed != null) parts.push(`${metrics.inputs_confirmed} inputs confirmed`)
  if (parts.length > 0) return parts.slice(0, 3).join(' · ')
  const estimate = formatEstimateFooter(node)
  if (estimate) return estimate
  return node.status
}

export function mapApiNodesToGraph(apiNodes: WorkflowNode[]): BdaWorkflowNode[] {
  const nodes: BdaWorkflowNode[] = apiNodes.map((node, index) => {
    const meta = NODE_META[node.node_type] ?? {
      icon: 'database',
      resource: 'local' as const,
      column: index,
    }
    return {
      id: node.id,
      type: 'workflowNode',
      position: parsePosition(node, index),
      data: {
        label:
          typeof node.parameters.display_name === 'string'
            ? node.parameters.display_name
            : node.node_key,
        description:
          typeof node.parameters.description === 'string'
            ? node.parameters.description
            : meta.description ?? node.node_key,
        icon: meta.icon,
        status: mapStatus(node.status),
        footer: footerFromMetrics(node),
        resource: meta.resource,
      },
    }
  })

  return nodes
}

export function mapApiGraphToGraph(apiNodes: WorkflowNode[], apiEdges: WorkflowEdge[]): {
  nodes: BdaWorkflowNode[]
  edges: BdaWorkflowEdge[]
} {
  return {
    nodes: mapApiNodesToGraph(apiNodes),
    edges: apiEdges.map((edge, index) => ({
      id: `edge-${index}-${edge.source}-${edge.target}`,
      source: apiNodes.find((node) => node.node_key === edge.source)?.id ?? edge.source,
      target: apiNodes.find((node) => node.node_key === edge.target)?.id ?? edge.target,
      sourceHandle: 'output',
      targetHandle: 'input',
      type: 'workflowEdge',
      markerEnd: { type: MarkerType.ArrowClosed, color: themeColor('--accent', '#D08A2A') },
      animated: false,
    })),
  }
}

export function mapStatusForTest(status: string): WorkflowNodeStatus {
  return mapStatus(status)
}
