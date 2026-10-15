import { ORDER_SOURCE_HANDLE, ORDER_TARGET_HANDLE, type BdaWorkflowEdge, type BdaWorkflowNode } from './workflowTypes'

/** Temporary overview layout: stored positions and dependency edges stay intact. */
export function workflowOverview(nodes: BdaWorkflowNode[], edges: BdaWorkflowEdge[]): { nodes: BdaWorkflowNode[]; edges: BdaWorkflowEdge[] } {
  const incoming = new Map(nodes.map(node => [node.id, 0]))
  const outgoing = new Map(nodes.map(node => [node.id, [] as string[]]))
  const depth = new Map(nodes.map(node => [node.id, 0]))
  for (const edge of edges) {
    if (!incoming.has(edge.source) || !incoming.has(edge.target)) continue
    outgoing.get(edge.source)!.push(edge.target)
    incoming.set(edge.target, incoming.get(edge.target)! + 1)
  }
  const queue = nodes.filter(node => incoming.get(node.id) === 0).map(node => node.id)
  for (let index = 0; index < queue.length; index++) {
    const source = queue[index]
    for (const target of outgoing.get(source)!) {
      depth.set(target, Math.max(depth.get(target)!, depth.get(source)! + 1))
      incoming.set(target, incoming.get(target)! - 1)
      if (incoming.get(target) === 0) queue.push(target)
    }
  }
  const hasTopology = edges.length > 0 && queue.length === nodes.length
  const linear = hasTopology && edges.length === nodes.length - 1 && new Set(depth.values()).size === nodes.length
  const rows = new Map<number, number>()
  // Edge-less imports still have phase positions from the mapper. Keep that visual
  // grouping instead of numbering the API's arbitrary response order.
  const ordered = edges.length ? nodes : [...nodes].sort((a, b) => a.position.x - b.position.x || a.position.y - b.position.y)
  const displayIndex = new Map(ordered.map((node, index) => [node.id, index]))
  const layout = new Map(nodes.map((node, index) => {
    if (!edges.length) index = displayIndex.get(node.id)!
    const rank = depth.get(node.id)!
    const row = linear ? Math.floor(rank / 3) : hasTopology ? rows.get(rank) ?? 0 : Math.floor(index / 4)
    rows.set(rank, row + 1)
    const column = linear ? (row % 2 ? 2 - rank % 3 : rank % 3) : hasTopology ? rank : index % 4
    return [node.id, { x: column * 390, y: row * 286 }]
  }))
  return {
    nodes: nodes.map(node => {
      return {
        ...node,
        // Cyclic routes keep their positions; the overview must not invent order.
        position: edges.length && !hasTopology ? node.position : layout.get(node.id)!,
        data: { ...node.data, overview: true, overviewLabel: String((linear ? depth.get(node.id)! : displayIndex.get(node.id)!) + 1).padStart(2, '0') },
      }
    }),
    edges: edges.map(edge => {
      const source = layout.get(edge.source)
      const target = layout.get(edge.target)
      const wrap = linear && source?.y !== target?.y
      const reverse = linear && source && target && source.x > target.x
      return {
        ...edge,
        sourceHandle: wrap ? '__overview_bottom' : reverse ? '__overview_out_left' : ORDER_SOURCE_HANDLE,
        targetHandle: wrap ? '__overview_top' : reverse ? '__overview_in_right' : ORDER_TARGET_HANDLE,
        data: { ...edge.data, overview: true },
        style: { ...edge.style, strokeWidth: 2 },
      }
    }),
  }
}
