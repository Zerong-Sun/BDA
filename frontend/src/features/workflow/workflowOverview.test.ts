import { describe, expect, it } from 'vitest'
import { workflowOverview } from './workflowOverview'
import { defaultWorkflowNodes, type BdaWorkflowEdge } from './workflowTypes'

describe('Workflow overview', () => {
  const nodes = Array.from({ length: 6 }, (_, index) => ({ ...defaultWorkflowNodes[0], id: `node-${index}`, position: { x: index * 20, y: 80 } }))
  const edges: BdaWorkflowEdge[] = nodes.slice(1).map((node, index) => ({ id: `edge-${index}`, source: nodes[index].id, target: node.id, sourceHandle: 'artifact', targetHandle: 'sequence', data: { gate: { mode: 'dependency' } } }))

  it('wraps a linear route without changing its dependencies or stored positions', () => {
    const overview = workflowOverview(nodes, edges)
    expect(overview.nodes[0].position).toEqual({ x: 0, y: 0 })
    expect(overview.nodes[3].position).toEqual({ x: 780, y: 286 })
    expect(overview.nodes[5].position).toEqual({ x: 0, y: 286 })
    expect(overview.edges[2].sourceHandle).toBe('__overview_bottom')
    expect(overview.edges[3].sourceHandle).toBe('__overview_out_left')
    expect(overview.edges.map(({ source, target }) => ({ source, target }))).toEqual(edges.map(({ source, target }) => ({ source, target })))
    expect(overview.edges[0].data?.gate).toEqual(edges[0].data?.gate)
    expect(nodes[3].position).toEqual({ x: 60, y: 80 })
    expect(edges[0].sourceHandle).toBe('artifact')
    expect(overview.nodes.map(node => node.data.status)).toEqual(nodes.map(node => node.data.status))
  })

  it('shows parallel branches on separate rows and keeps cyclic routes in place', () => {
    const branching = [edges[0], { ...edges[1], source: nodes[0].id }]
    const graph = workflowOverview(nodes.slice(0, 3), branching)
    expect(graph.nodes[1].position.x).toBe(graph.nodes[2].position.x)
    expect(graph.nodes[1].position.y).not.toBe(graph.nodes[2].position.y)
    const cyclic = workflowOverview(nodes.slice(0, 2), [edges[0], { id: 'cycle', source: nodes[1].id, target: nodes[0].id }])
    expect(cyclic.nodes.map(node => node.position)).toEqual(nodes.slice(0, 2).map(node => node.position))
  })

  it('never invents arrows for an imported record without dependencies', () => {
    const graph = workflowOverview(nodes, [])
    expect(graph.edges).toEqual([])
    expect(graph.nodes[4].position).toEqual({ x: 0, y: 286 })
    const shuffled = workflowOverview([nodes[3], nodes[1], nodes[2], nodes[0]], [])
    expect(shuffled.nodes.find(node => node.id === nodes[0].id)?.data.overviewLabel).toBe('01')
  })
})
